"""FastAPI endpoints for Gym Mode voice parsing, exercise taxonomy, and atomic set persistence."""

from datetime import datetime, timedelta, timezone
from typing import Literal
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.deps import get_or_create_default_user
from src.models.exercise import StrengthExercise
from src.models.strength_set import StrengthSet
from src.models.voice_log import VoiceTranscriptionLog
from src.models.workout import WorkoutSession
from src.schemas.gym import (
    CommitSetsRequest,
    ParseTranscriptRequest,
    ParsedSetCandidate,
    ParsedStageResponse,
    StrengthExerciseResponse,
    StrengthSetResponse,
)
from src.schemas.workout import WorkoutSessionResponse
from src.services.exercise_catalog import catalog_service
from src.services.gym_parser import gym_parser

router = APIRouter(prefix="/api/v1/gym", tags=["Gym Mode"])


def _to_set_response(s: StrengthSet, fallback_name: str = "Unknown Exercise") -> StrengthSetResponse:
    return StrengthSetResponse(
        id=s.id,
        workout_session_id=s.workout_session_id,
        exercise_id=s.exercise_id,
        exercise_name=s.exercise.canonical_name if s.exercise else fallback_name,
        set_index=s.set_index,
        reps_completed=s.reps_completed,
        target_reps=s.target_reps,
        weight=float(s.weight),
        weight_unit=s.weight_unit,
        is_bodyweight=s.is_bodyweight,
        added_weight=float(s.added_weight),
        rpe=float(s.rpe) if s.rpe is not None else None,
        is_warmup=s.is_warmup,
        rest_seconds=s.rest_seconds,
        completed_at=s.completed_at,
    )


async def _resolve_or_seed_exercise(db: AsyncSession, candidate: ParsedSetCandidate) -> StrengthExercise:
    """Resolve an exercise by ID, slug, catalog fuzzy match, or canonical name, seeding deterministically if needed."""
    # 1. Explicit exercise_id lookup
    if candidate.exercise_id is not None:
        res = await db.execute(select(StrengthExercise).where(StrengthExercise.id == candidate.exercise_id))
        existing = res.scalar_one_or_none()
        if existing is not None:
            return existing

    # 2. Try in-memory catalog match by exercise_name
    entry, _, _ = catalog_service.find_match(candidate.exercise_name, min_score=70.0)
    if entry is not None:
        # Look up in DB by either deterministic ID OR slug (handles legacy/seeded UUIDs safely)
        res = await db.execute(
            select(StrengthExercise).where(
                or_(
                    StrengthExercise.id == entry.id,
                    StrengthExercise.slug == entry.slug,
                )
            )
        )
        existing = res.scalar_one_or_none()
        if existing is not None:
            return existing

        ex_obj = StrengthExercise(
            id=entry.id,
            canonical_name=entry.canonical_name,
            slug=entry.slug,
            category=entry.category,
            primary_muscle_group=entry.primary_muscle_group,
            is_bodyweight=entry.is_bodyweight,
            default_unit=entry.default_unit,
        )
        db.add(ex_obj)
        await db.flush()
        return ex_obj

    # 3. Direct DB fallback by canonical_name or slug
    cleaned = candidate.exercise_name.strip()
    slug_guess = cleaned.lower().replace(" ", "-")
    res = await db.execute(
        select(StrengthExercise).where(
            or_(
                StrengthExercise.canonical_name.ilike(cleaned),
                StrengthExercise.slug == slug_guess,
            )
        )
    )
    db_ex = res.scalar_one_or_none()
    if db_ex is not None:
        return db_ex

    raise HTTPException(
        status_code=400,
        detail=f"Unrecognized exercise: {candidate.exercise_name}",
    )


@router.post("/parse", response_model=ParsedStageResponse)
async def parse_gym_transcript(payload: ParseTranscriptRequest):
    """Parses spoken natural language transcript into structured set candidates."""
    return gym_parser.parse(payload.transcript, default_unit=payload.default_unit)


@router.get("/exercises", response_model=list[StrengthExerciseResponse])
async def list_exercises(
    query: str | None = None,
    category: Literal["barbell", "dumbbell", "bodyweight", "machine", "cable"] | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Lists catalog exercises with optional category and search filters."""
    q = select(StrengthExercise).options(selectinload(StrengthExercise.aliases))
    if category:
        q = q.where(StrengthExercise.category == category)
    if query:
        search_term = f"%{query.strip().lower()}%"
        q = q.where(
            (StrengthExercise.canonical_name.ilike(search_term))
            | (StrengthExercise.slug.ilike(search_term))
        )

    res = await db.execute(q)
    exercises = res.scalars().all()

    if not exercises and not query and not category:
        entries = catalog_service.get_all_entries()
        return [
            StrengthExerciseResponse(
                id=e.id,
                canonical_name=e.canonical_name,
                slug=e.slug,
                category=e.category,
                primary_muscle_group=e.primary_muscle_group,
                is_bodyweight=e.is_bodyweight,
                default_unit=e.default_unit,
                aliases=e.aliases,
            )
            for e in entries
        ]

    return [
        StrengthExerciseResponse(
            id=ex.id,
            canonical_name=ex.canonical_name,
            slug=ex.slug,
            category=ex.category,
            primary_muscle_group=ex.primary_muscle_group,
            is_bodyweight=ex.is_bodyweight,
            default_unit=ex.default_unit,
            aliases=[a.alias for a in ex.aliases],
        )
        for ex in exercises
    ]


async def _find_active_strength_session(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> WorkoutSession | None:
    """Finds an active strength session for the user started within the last 4 hours."""
    recent_cutoff = now - timedelta(hours=4)
    q = (
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.discipline == "strength",
            WorkoutSession.status == "active",
            WorkoutSession.start_time_utc >= recent_cutoff,
        )
        .order_by(desc(WorkoutSession.start_time_utc))
    )
    res = await db.execute(q)
    return res.scalars().first()


def _create_gym_session(user_id: uuid.UUID, user_timezone: str | None, now: datetime) -> WorkoutSession:
    """Instantiates a new strength WorkoutSession titled in the athlete's configured local timezone."""
    try:
        tz = ZoneInfo(user_timezone or "UTC")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    local_now = now.astimezone(tz)
    return WorkoutSession(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="coach3_gym",
        external_id=f"gym_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
        discipline="strength",
        title=f"Gym Strength Session {local_now.strftime('%b %d')}",
        start_time_utc=now,
        local_timezone=user_timezone or "UTC",
        total_duration_sec=0.0,
        active_duration_sec=0.0,
        total_distance_m=0.0,
        status="active",
    )


@router.get("/sessions/active", response_model=WorkoutSessionResponse | None)
async def get_active_strength_session(db: AsyncSession = Depends(get_db)):
    """Read-only lookup for an ongoing strength workout session within the last 4 hours."""
    user = await get_or_create_default_user(db)
    now = datetime.now(timezone.utc)
    return await _find_active_strength_session(db, user.id, now)


@router.get("/sessions/{session_id}/sets", response_model=list[StrengthSetResponse])
async def list_session_sets(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Returns all committed strength sets for a session ordered by set_index."""
    user = await get_or_create_default_user(db)
    sess_q = select(WorkoutSession).where(
        WorkoutSession.id == session_id,
        WorkoutSession.user_id == user.id,
    )
    sess_res = await db.execute(sess_q)
    if sess_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Workout session {session_id} not found")

    q = (
        select(StrengthSet)
        .options(selectinload(StrengthSet.exercise))
        .where(StrengthSet.workout_session_id == session_id)
        .order_by(StrengthSet.set_index)
    )
    res = await db.execute(q)
    return [_to_set_response(s) for s in res.scalars().all()]


async def _commit_sets_impl(
    db: AsyncSession,
    payload: CommitSetsRequest,
    explicit_session_id: uuid.UUID | None = None,
) -> list[StrengthSetResponse]:
    """Atomically commits confirmed strength sets with exact submission-level idempotency and lazy session creation."""
    user = await get_or_create_default_user(db)
    target_session_id = explicit_session_id or payload.session_id

    # 1. Exact Submission Idempotency Check (scoped to user, or session if explicitly provided)
    existing_filters = [
        StrengthSet.submission_key == payload.idempotency_key,
        WorkoutSession.user_id == user.id,
    ]
    if target_session_id is not None:
        existing_filters.append(StrengthSet.workout_session_id == target_session_id)

    existing_q = (
        select(StrengthSet)
        .join(WorkoutSession, StrengthSet.workout_session_id == WorkoutSession.id)
        .options(selectinload(StrengthSet.exercise))
        .where(*existing_filters)
        .order_by(StrengthSet.set_index)
    )
    existing_res = await db.execute(existing_q)
    existing_sets = existing_res.scalars().all()
    if existing_sets:
        return [_to_set_response(s) for s in existing_sets]

    now = datetime.now(timezone.utc)

    # 2. Resolve explicit session OR lazily find/create an active strength session
    if target_session_id is not None:
        sess_q = select(WorkoutSession).where(
            WorkoutSession.id == target_session_id,
            WorkoutSession.user_id == user.id,
        )
        sess_res = await db.execute(sess_q)
        session = sess_res.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail=f"Workout session {target_session_id} not found")
    else:
        session = await _find_active_strength_session(db, user.id, now)
        if session is None:
            session = _create_gym_session(user.id, user.timezone, now)
            db.add(session)
            await db.flush()

    session_id = session.id

    # 3. Determine current highest set_index in session
    idx_q = (
        select(StrengthSet.set_index)
        .where(StrengthSet.workout_session_id == session_id)
        .order_by(desc(StrengthSet.set_index))
    )
    idx_res = await db.execute(idx_q)
    highest_idx = idx_res.scalars().first() or 0

    created_sets: list[StrengthSet] = []
    seq = 0

    for candidate in payload.sets:
        ex_obj = await _resolve_or_seed_exercise(db, candidate)
        ex_id = ex_obj.id

        for _ in range(candidate.sets):
            highest_idx += 1
            seq += 1
            item_key = f"{payload.idempotency_key}:{seq}"
            s_row = StrengthSet(
                id=uuid.uuid4(),
                workout_session_id=session_id,
                exercise_id=ex_id,
                set_index=highest_idx,
                reps_completed=candidate.reps,
                target_reps=candidate.target_reps,
                weight=0.0 if candidate.is_bodyweight else candidate.weight,
                weight_unit=candidate.weight_unit,
                is_bodyweight=candidate.is_bodyweight,
                added_weight=candidate.added_weight,
                rpe=candidate.rpe,
                is_warmup=candidate.is_warmup,
                rest_seconds=candidate.rest_seconds,
                submission_key=payload.idempotency_key,
                idempotency_key=item_key,
                completed_at=now,
            )
            db.add(s_row)
            created_sets.append(s_row)

    # 4. Record Voice Transcription Audit Log with distinct parsed vs final_confirmed payloads
    if payload.raw_transcript:
        parsed_source = payload.original_parsed_sets if payload.original_parsed_sets is not None else payload.sets
        v_log = VoiceTranscriptionLog(
            id=uuid.uuid4(),
            user_id=user.id,
            workout_session_id=session_id,
            raw_transcript=payload.raw_transcript,
            parsed_json=[s.model_dump(mode="json") for s in parsed_source],
            confidence_score=payload.confidence_score or 1.0,
            was_edited=payload.was_edited,
            final_confirmed_json=[s.model_dump(mode="json") for s in payload.sets],
            confirmed_at=now,
        )
        db.add(v_log)

    await db.flush()

    result_q = (
        select(StrengthSet)
        .options(selectinload(StrengthSet.exercise))
        .where(StrengthSet.id.in_([s.id for s in created_sets]))
        .order_by(StrengthSet.set_index)
    )
    result_res = await db.execute(result_q)
    saved_sets = result_res.scalars().all()

    return [_to_set_response(s) for s in saved_sets]


@router.post("/sets", response_model=list[StrengthSetResponse], status_code=status.HTTP_201_CREATED)
async def commit_strength_sets_lazy(
    payload: CommitSetsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Commits confirmed strength sets, lazily creating or reusing an active strength session."""
    return await _commit_sets_impl(db, payload)


@router.post("/sessions/{session_id}/sets", response_model=list[StrengthSetResponse], status_code=status.HTTP_201_CREATED)
async def commit_strength_sets(
    session_id: uuid.UUID,
    payload: CommitSetsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Atomically commits confirmed strength sets to an explicit session."""
    return await _commit_sets_impl(db, payload, explicit_session_id=session_id)


@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strength_set(
    set_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Deletes a single strength set and cleans up the parent gym session if it becomes empty."""
    user = await get_or_create_default_user(db)
    stmt = (
        select(StrengthSet)
        .join(WorkoutSession, StrengthSet.workout_session_id == WorkoutSession.id)
        .where(
            StrengthSet.id == set_id,
            WorkoutSession.user_id == user.id,
        )
    )
    res = await db.execute(stmt)
    s_row = res.scalar_one_or_none()
    if s_row is None:
        raise HTTPException(status_code=404, detail="Strength set not found")

    parent_session_id = s_row.workout_session_id
    await db.delete(s_row)
    await db.flush()

    remaining_count = (
        await db.execute(
            select(func.count(StrengthSet.id)).where(StrengthSet.workout_session_id == parent_session_id)
        )
    ).scalar() or 0
    if remaining_count == 0:
        sess_res = await db.execute(
            select(WorkoutSession).where(
                WorkoutSession.id == parent_session_id,
                WorkoutSession.user_id == user.id,
                WorkoutSession.provider == "coach3_gym",
            )
        )
        parent_sess = sess_res.scalar_one_or_none()
        if parent_sess is not None:
            await db.delete(parent_sess)
            await db.flush()

    return None

