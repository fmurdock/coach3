"""FastAPI endpoints for Adaptive AI Coaching Engine, Dual-Engine LLMs, and Philosophies."""

from datetime import datetime, timezone
from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.deps import get_or_create_default_user
from src.core.security import encrypt_token
from src.models.coaching import (
    CoachingCritique,
    CoachingPhilosophy,
    LLMProviderConfig,
    ScheduledWorkout,
    TrainingSchedulePlan,
)
from src.schemas.coaching import (
    AnalyzeWorkoutRequest,
    CoachingCritiqueResponse,
    CoachingPhilosophyResponse,
    GeneratePlanRequest,
    LLMProviderResponse,
    ProviderHealthResponse,
    SavePhilosophyRequest,
    SaveProviderRequest,
    ScheduledWorkoutItem,
    ScheduledWorkoutUpdateRequest,
    TrainingSchedulePlanResponse,
)
from src.services.coaching_service import CoachingBusyError, CoachingService
from src.services.llm_client import get_llm_client_for_config
from src.services.philosophy_service import PhilosophyService

router = APIRouter(prefix="/api/v1/coaching", tags=["Adaptive AI Coaching"])
coaching_service = CoachingService()


def _to_scheduled_item(w: ScheduledWorkout) -> ScheduledWorkoutItem:
    return ScheduledWorkoutItem(
        id=w.id,
        target_date=w.target_date,
        discipline=w.discipline,
        title=w.title,
        planned_duration_min=w.planned_duration_min,
        target_distance_m=float(w.target_distance_m) if w.target_distance_m is not None else None,
        target_zone=w.target_zone,
        target_rpe=float(w.target_rpe) if w.target_rpe is not None else None,
        strength_exercises=w.strength_exercises,
        notes=w.notes,
        is_completed=w.is_completed,
    )


# --- Provider Endpoints ---

@router.get("/providers", response_model=List[LLMProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    """Lists configured LLM inference providers."""
    user = await get_or_create_default_user(db)
    stmt = (
        select(LLMProviderConfig)
        .where(LLMProviderConfig.user_id == user.id)
        .order_by(LLMProviderConfig.created_at.asc())
    )
    res = await db.execute(stmt)
    providers = res.scalars().all()
    return [
        LLMProviderResponse(
            id=p.id,
            provider_type=p.provider_type,
            endpoint_url=p.endpoint_url,
            model_name=p.model_name,
            temperature=float(p.temperature),
            max_tokens=p.max_tokens,
            is_active=p.is_active,
            has_api_key=bool(p.api_key_encrypted),
        )
        for p in providers
    ]


@router.post("/providers", response_model=LLMProviderResponse)
async def save_provider(payload: SaveProviderRequest, db: AsyncSession = Depends(get_db)):
    """Creates or updates an LLM provider configuration."""
    user = await get_or_create_default_user(db)

    stmt = select(LLMProviderConfig).where(
        and_(
            LLMProviderConfig.user_id == user.id,
            LLMProviderConfig.provider_type == payload.provider_type,
        )
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.endpoint_url = payload.endpoint_url
        existing.model_name = payload.model_name
        existing.temperature = payload.temperature
        existing.max_tokens = payload.max_tokens
        if payload.api_key:
            existing.api_key_encrypted = encrypt_token(payload.api_key)
        await db.flush()
        await db.refresh(existing)
        return LLMProviderResponse(
            id=existing.id,
            provider_type=existing.provider_type,
            endpoint_url=existing.endpoint_url,
            model_name=existing.model_name,
            temperature=float(existing.temperature),
            max_tokens=existing.max_tokens,
            is_active=existing.is_active,
            has_api_key=bool(existing.api_key_encrypted),
        )

    stmt_any_active = select(LLMProviderConfig).where(
        and_(
            LLMProviderConfig.user_id == user.id,
            LLMProviderConfig.is_active.is_(True),
        )
    )
    res_active = await db.execute(stmt_any_active)
    has_active = res_active.scalar_one_or_none() is not None

    new_provider = LLMProviderConfig(
        id=uuid.uuid4(),
        user_id=user.id,
        provider_type=payload.provider_type,
        endpoint_url=payload.endpoint_url,
        api_key_encrypted=encrypt_token(payload.api_key) if payload.api_key else None,
        model_name=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        is_active=not has_active,
    )
    db.add(new_provider)
    await db.flush()
    await db.refresh(new_provider)

    return LLMProviderResponse(
        id=new_provider.id,
        provider_type=new_provider.provider_type,
        endpoint_url=new_provider.endpoint_url,
        model_name=new_provider.model_name,
        temperature=float(new_provider.temperature),
        max_tokens=new_provider.max_tokens,
        is_active=new_provider.is_active,
        has_api_key=bool(new_provider.api_key_encrypted),
    )


@router.post("/providers/{provider_id}/activate", response_model=LLMProviderResponse)
async def activate_provider(provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Sets the active inference provider and deactivates others."""
    user = await get_or_create_default_user(db)
    stmt = select(LLMProviderConfig).where(
        and_(
            LLMProviderConfig.id == provider_id,
            LLMProviderConfig.user_id == user.id,
        )
    )
    res = await db.execute(stmt)
    provider = res.scalar_one_or_none()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    await db.execute(
        update(LLMProviderConfig)
        .where(LLMProviderConfig.user_id == user.id)
        .values(is_active=False)
    )

    provider.is_active = True
    await db.flush()
    await db.refresh(provider)

    return LLMProviderResponse(
        id=provider.id,
        provider_type=provider.provider_type,
        endpoint_url=provider.endpoint_url,
        model_name=provider.model_name,
        temperature=float(provider.temperature),
        max_tokens=provider.max_tokens,
        is_active=provider.is_active,
        has_api_key=bool(provider.api_key_encrypted),
    )


@router.post("/providers/{provider_id}/test", response_model=ProviderHealthResponse)
async def test_provider_health(provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Tests connectivity and latency for an inference provider."""
    user = await get_or_create_default_user(db)
    stmt = select(LLMProviderConfig).where(
        and_(
            LLMProviderConfig.id == provider_id,
            LLMProviderConfig.user_id == user.id,
        )
    )
    res = await db.execute(stmt)
    provider = res.scalar_one_or_none()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    try:
        client = get_llm_client_for_config(
            provider_type=provider.provider_type,
            endpoint_url=provider.endpoint_url,
            api_key_encrypted=provider.api_key_encrypted,
            model_name=provider.model_name,
            temperature=float(provider.temperature),
            max_tokens=provider.max_tokens,
        )
    except ValueError as exc:
        return ProviderHealthResponse(status="invalid_credentials", latency_ms=0.0, message=str(exc))

    return await client.test_connection()


# --- Philosophy Endpoints ---

@router.get("/philosophies", response_model=List[CoachingPhilosophyResponse])
async def list_philosophies(db: AsyncSession = Depends(get_db)):
    """Lists coaching philosophies with presets seeded if needed."""
    user = await get_or_create_default_user(db)
    philosophies = await PhilosophyService.list_philosophies(db, user.id)
    return [
        CoachingPhilosophyResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            target_zone2_pct=float(p.target_zone2_pct),
            max_weekly_volume_ramp_pct=float(p.max_weekly_volume_ramp_pct),
            max_rpe_threshold=float(p.max_rpe_threshold),
            min_rest_days_per_week=p.min_rest_days_per_week,
            primary_modality=p.primary_modality,
            custom_context_notes=p.custom_context_notes,
            is_active=p.is_active,
        )
        for p in philosophies
    ]


@router.post("/philosophies", response_model=CoachingPhilosophyResponse)
async def save_philosophy(payload: SavePhilosophyRequest, db: AsyncSession = Depends(get_db)):
    """Creates or updates a coaching philosophy."""
    user = await get_or_create_default_user(db)
    phil = await PhilosophyService.save_philosophy(db, user.id, payload)
    return CoachingPhilosophyResponse(
        id=phil.id,
        name=phil.name,
        description=phil.description,
        target_zone2_pct=float(phil.target_zone2_pct),
        max_weekly_volume_ramp_pct=float(phil.max_weekly_volume_ramp_pct),
        max_rpe_threshold=float(phil.max_rpe_threshold),
        min_rest_days_per_week=phil.min_rest_days_per_week,
        primary_modality=phil.primary_modality,
        custom_context_notes=phil.custom_context_notes,
        is_active=phil.is_active,
    )


@router.post("/philosophies/{philosophy_id}/activate", response_model=CoachingPhilosophyResponse)
async def activate_philosophy(philosophy_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Sets a philosophy as active."""
    user = await get_or_create_default_user(db)
    try:
        phil = await PhilosophyService.activate_philosophy(db, user.id, philosophy_id)
        return CoachingPhilosophyResponse(
            id=phil.id,
            name=phil.name,
            description=phil.description,
            target_zone2_pct=float(phil.target_zone2_pct),
            max_weekly_volume_ramp_pct=float(phil.max_weekly_volume_ramp_pct),
            max_rpe_threshold=float(phil.max_rpe_threshold),
            min_rest_days_per_week=phil.min_rest_days_per_week,
            primary_modality=phil.primary_modality,
            custom_context_notes=phil.custom_context_notes,
            is_active=phil.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# --- Analysis & Planning Endpoints ---

@router.post("/analyze", response_model=CoachingCritiqueResponse)
async def analyze_workout(payload: AnalyzeWorkoutRequest, db: AsyncSession = Depends(get_db)):
    """Runs retrospective workout analysis against active coaching philosophy."""
    user = await get_or_create_default_user(db)

    phil = None
    if payload.philosophy_id:
        stmt = select(CoachingPhilosophy).where(
            and_(
                CoachingPhilosophy.id == payload.philosophy_id,
                CoachingPhilosophy.user_id == user.id,
            )
        )
        res = await db.execute(stmt)
        phil = res.scalar_one_or_none()
        if not phil:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Philosophy {payload.philosophy_id} not found",
            )

    start_dt = (
        datetime.combine(payload.start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        if payload.start_date
        else None
    )
    end_dt = (
        datetime.combine(payload.end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        if payload.end_date
        else None
    )

    try:
        critique = await coaching_service.analyze_workout(
            session=db,
            user_id=user.id,
            workout_session_id=payload.workout_session_id,
            start_date=start_dt,
            end_date=end_dt,
            philosophy=phil,
        )
        return CoachingCritiqueResponse(
            id=critique.id,
            provider_used=critique.provider_used,
            adherence_score=float(critique.adherence_score),
            summary_markdown=critique.summary_markdown,
            adherence_details=critique.adherence_details,
            strain_assessment=critique.strain_assessment,
            recommendations=critique.recommendations,
            created_at=critique.created_at,
        )
    except CoachingBusyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM inference error: {str(e)}",
        ) from e


@router.post("/plan", response_model=TrainingSchedulePlanResponse)
async def generate_forward_plan(payload: GeneratePlanRequest, db: AsyncSession = Depends(get_db)):
    """Generates periodized forward schedule plan (Planning Mode)."""
    user = await get_or_create_default_user(db)

    phil = None
    if payload.philosophy_id:
        stmt = select(CoachingPhilosophy).where(
            and_(
                CoachingPhilosophy.id == payload.philosophy_id,
                CoachingPhilosophy.user_id == user.id,
            )
        )
        res = await db.execute(stmt)
        phil = res.scalar_one_or_none()
        if not phil:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Philosophy {payload.philosophy_id} not found",
            )

    try:
        plan = await coaching_service.generate_forward_plan(
            session=db,
            user_id=user.id,
            target_goal=payload.target_goal,
            horizon_days=payload.horizon_days,
            available_days_per_week=payload.available_days_per_week,
            philosophy=phil,
            tz_name=user.timezone or "UTC",
        )
        return TrainingSchedulePlanResponse(
            id=plan.id,
            target_goal=plan.target_goal,
            start_date=plan.start_date,
            end_date=plan.end_date,
            horizon_days=plan.horizon_days,
            summary_markdown=plan.summary_markdown,
            status=plan.status,
            scheduled_workouts=[_to_scheduled_item(w) for w in plan.scheduled_workouts],
        )
    except CoachingBusyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM inference error: {str(e)}",
        ) from e


@router.get("/plans/active", response_model=TrainingSchedulePlanResponse)
async def get_active_plan(db: AsyncSession = Depends(get_db)):
    """Retrieves currently active forward schedule plan and workouts."""
    user = await get_or_create_default_user(db)
    stmt = (
        select(TrainingSchedulePlan)
        .options(selectinload(TrainingSchedulePlan.scheduled_workouts))
        .where(
            and_(
                TrainingSchedulePlan.user_id == user.id,
                TrainingSchedulePlan.status == "active",
            )
        )
        .order_by(TrainingSchedulePlan.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    plan = res.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active training schedule plan found",
        )

    return TrainingSchedulePlanResponse(
        id=plan.id,
        target_goal=plan.target_goal,
        start_date=plan.start_date,
        end_date=plan.end_date,
        horizon_days=plan.horizon_days,
        summary_markdown=plan.summary_markdown,
        status=plan.status,
        scheduled_workouts=[_to_scheduled_item(w) for w in plan.scheduled_workouts],
    )


@router.patch("/scheduled-workouts/{scheduled_workout_id}", response_model=ScheduledWorkoutItem)
async def update_scheduled_workout(
    scheduled_workout_id: uuid.UUID,
    payload: ScheduledWorkoutUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Toggle completion status on a planned workout item."""
    user = await get_or_create_default_user(db)
    stmt = (
        select(ScheduledWorkout)
        .join(TrainingSchedulePlan, ScheduledWorkout.plan_id == TrainingSchedulePlan.id)
        .where(
            ScheduledWorkout.id == scheduled_workout_id,
            TrainingSchedulePlan.user_id == user.id,
        )
    )
    res = await db.execute(stmt)
    scheduled = res.scalar_one_or_none()
    if not scheduled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled workout not found",
        )
    scheduled.is_completed = payload.is_completed
    await db.flush()
    await db.refresh(scheduled)
    return _to_scheduled_item(scheduled)


@router.get("/critiques/recent", response_model=List[CoachingCritiqueResponse])
async def list_recent_critiques(
    limit: int = Query(default=5, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves recent workout critiques (bounded 1..100)."""
    user = await get_or_create_default_user(db)
    stmt = (
        select(CoachingCritique)
        .where(CoachingCritique.user_id == user.id)
        .order_by(CoachingCritique.created_at.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    critiques = res.scalars().all()
    return [
        CoachingCritiqueResponse(
            id=c.id,
            provider_used=c.provider_used,
            adherence_score=float(c.adherence_score),
            summary_markdown=c.summary_markdown,
            adherence_details=c.adherence_details,
            strain_assessment=c.strain_assessment,
            recommendations=c.recommendations,
            created_at=c.created_at,
        )
        for c in critiques
    ]
