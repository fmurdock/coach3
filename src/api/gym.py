"""FastAPI endpoints for Gym Mode voice parsing, exercise taxonomy, and atomic set persistence."""

from datetime import datetime, timedelta, timezone
from typing import Literal
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models.exercise import ExerciseAlias, StrengthExercise
from src.models.strength_set import StrengthSet
from src.models.user import User
from src.models.voice_log import VoiceTranscriptionLog
from src.models.workout import WorkoutSession
from src.schemas.gym import (
    CommitSetsRequest,
    ParseTranscriptRequest,
    ParsedStageResponse,
    StrengthExerciseResponse,
    StrengthSetResponse,
)
from src.schemas.workout import WorkoutSessionResponse
from src.services.exercise_catalog import catalog_service
from src.services.gym_parser import gym_parser

router = APIRouter(prefix="/api/v1/gym", tags=["Gym Mode"])


async def get_or_create_default_user(db: AsyncSession) -> User:
    """Helper for single-user self-hosted mode: retrieves or seeds default user."""
    res = await db.execute(select(User))
    user = res.scalars().first()
    if not user:
        user = User(id=uuid.uuid4())
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


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
        # If DB not yet seeded, return from in-memory catalog
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


@router.get("/sessions/active", response_model=WorkoutSessionResponse)
async def get_or_create_active_strength_session(db: AsyncSession = Depends(get_db)):
    """Retrieves an ongoing strength workout session or creates a new one."""
    user = await get_or_create_default_user(db)
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=4)

    q = (
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.discipline == "strength",
            WorkoutSession.start_time_utc >= recent_cutoff,
        )
        .order_by(desc(WorkoutSession.start_time_utc))
    )
    res = await db.execute(q)
    session = res.scalars().first()

    if not session:
        session = WorkoutSession(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="coach3_gym",
            external_id=f"gym_{now.strftime('%Y%m%d_%H%M%S')}",
            discipline="strength",
            title=f"Gym Strength Session {now.strftime('%b %d')}",
            start_time_utc=now,
            local_timezone="UTC",
            total_duration_sec=0.0,
            active_duration_sec=0.0,
            total_distance_m=0.0,
            status="active",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return session


@router.post("/sessions/{session_id}/sets", response_model=list[StrengthSetResponse], status_code=status.HTTP_201_CREATED)
async def commit_strength_sets(
    session_id: uuid.UUID,
    payload: CommitSetsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Atomically commits confirmed strength sets to a session with idempotency protection."""
    user = await get_or_create_default_user(db)

    # 1. Idempotency Check
    if payload.idempotency_key:
        existing_q = (
            select(StrengthSet)
            .options(selectinload(StrengthSet.exercise))
            .where(
                StrengthSet.workout_session_id == session_id,
                StrengthSet.idempotency_key.like(f"{payload.idempotency_key}%"),
            )
            .order_by(StrengthSet.set_index)
        )
        existing_res = await db.execute(existing_q)
        existing_sets = existing_res.scalars().all()
        if existing_sets:
            return [
                StrengthSetResponse(
                    id=s.id,
                    workout_session_id=s.workout_session_id,
                    exercise_id=s.exercise_id,
                    exercise_name=s.exercise.canonical_name if s.exercise else "Unknown Exercise",
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
                for s in existing_sets
            ]

    # 2. Verify Session exists
    sess_q = select(WorkoutSession).where(WorkoutSession.id == session_id)
    sess_res = await db.execute(sess_q)
    session = sess_res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail=f"Workout session {session_id} not found")

    # 3. Determine current highest set_index in session
    idx_q = (
        select(StrengthSet.set_index)
        .where(StrengthSet.workout_session_id == session_id)
        .order_by(desc(StrengthSet.set_index))
    )
    idx_res = await db.execute(idx_q)
    highest_idx = idx_res.scalars().first() or 0

    now = datetime.now(timezone.utc)
    created_sets: list[StrengthSet] = []

    for candidate in payload.sets:
        # Resolve exercise_id if missing or check catalog
        ex_id = candidate.exercise_id
        if not ex_id:
            entry, _, _ = catalog_service.find_match(candidate.exercise_name)
            if entry:
                ex_id = entry.id
            else:
                # Fallback: query DB by name
                ex_q = select(StrengthExercise).where(StrengthExercise.canonical_name == candidate.exercise_name)
                ex_res = await db.execute(ex_q)
                db_ex = ex_res.scalar_one_or_none()
                if db_ex:
                    ex_id = db_ex.id
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unrecognized exercise: {candidate.exercise_name}",
                    )

        # Ensure exercise exists in DB or create entry if using deterministic namespace UUID
        ex_check = await db.execute(select(StrengthExercise).where(StrengthExercise.id == ex_id))
        ex_obj = ex_check.scalar_one_or_none()
        if not ex_obj:
            # Seed entry from catalog
            entry, _, _ = catalog_service.find_match(candidate.exercise_name)
            if entry:
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

        # Generate individual set rows for candidate.sets count
        for i in range(candidate.sets):
            highest_idx += 1
            # Base idempotency key for first set or indexed key
            item_key = payload.idempotency_key if (i == 0 and candidate.sets == 1) else f"{payload.idempotency_key}_{highest_idx}"
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
                idempotency_key=item_key,
                completed_at=now,
            )
            db.add(s_row)
            created_sets.append(s_row)

    # 4. Record Voice Transcription Audit Log
    if payload.raw_transcript:
        v_log = VoiceTranscriptionLog(
            id=uuid.uuid4(),
            user_id=user.id,
            workout_session_id=session_id,
            raw_transcript=payload.raw_transcript,
            parsed_json=[s.model_dump(mode="json") for s in payload.sets],
            confidence_score=payload.confidence_score or 1.0,
            was_edited=payload.was_edited,
            final_confirmed_json=[s.model_dump(mode="json") for s in payload.sets],
            confirmed_at=now,
        )
        db.add(v_log)

    await db.commit()

    # Re-fetch with exercise eager loaded
    result_q = (
        select(StrengthSet)
        .options(selectinload(StrengthSet.exercise))
        .where(StrengthSet.id.in_([s.id for s in created_sets]))
        .order_by(StrengthSet.set_index)
    )
    result_res = await db.execute(result_q)
    saved_sets = result_res.scalars().all()

    return [
        StrengthSetResponse(
            id=s.id,
            workout_session_id=s.workout_session_id,
            exercise_id=s.exercise_id,
            exercise_name=s.exercise.canonical_name if s.exercise else candidate.exercise_name,
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
        for s in saved_sets
    ]
