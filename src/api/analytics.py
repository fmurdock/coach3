"""FastAPI endpoints for Training Volume and Peak Performance Analytics."""

from datetime import date
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.user import User
from src.schemas.analytics import (
    CardioAnalyticsResponse,
    DashboardMacroResponse,
    PersonalRecordItem,
    StrengthAnalyticsResponse,
    UnifiedVolumeSummary,
    WindowPreset,
)
from src.services.analytics_service import AnalyticsService
from src.services.pr_detector import PRDetectorService

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])
analytics_service = AnalyticsService()
pr_detector = PRDetectorService()


@router.get("/dashboard", response_model=DashboardMacroResponse)
async def get_dashboard_macro(
    window: Optional[WindowPreset] = Query(default=WindowPreset.THIRTY_DAYS),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve unified macro training volume: Cardio (Zone 2 vs Zone 5 VO2 max) and Resistance muscle group sets with top weights."""
    user = await get_or_create_default_user(db)
    start_dt, end_dt = analytics_service.resolve_date_window(window, start_date, end_date)
    return await analytics_service.get_macro_dashboard_volume(db, user.id, start_dt, end_dt)


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


@router.get("/cardio", response_model=CardioAnalyticsResponse)
async def get_cardio_analytics(
    window: Optional[WindowPreset] = Query(default=WindowPreset.THIRTY_DAYS),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed cardiovascular volume and Zone 2 trends."""
    user = await get_or_create_default_user(db)
    start_dt, end_dt = analytics_service.resolve_date_window(window, start_date, end_date)
    return await analytics_service.get_cardio_metrics(db, user.id, start_dt, end_dt)


@router.get("/strength", response_model=StrengthAnalyticsResponse)
async def get_strength_analytics(
    window: Optional[WindowPreset] = Query(default=WindowPreset.THIRTY_DAYS),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve strength volume load, effective sets, and muscle group distributions."""
    user = await get_or_create_default_user(db)
    start_dt, end_dt = analytics_service.resolve_date_window(window, start_date, end_date)
    return await analytics_service.get_strength_metrics(db, user.id, start_dt, end_dt)


@router.get("/summary", response_model=UnifiedVolumeSummary)
async def get_unified_summary(
    window: Optional[WindowPreset] = Query(default=WindowPreset.THIRTY_DAYS),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve unified summary across cardio and strength."""
    user = await get_or_create_default_user(db)
    start_dt, end_dt = analytics_service.resolve_date_window(window, start_date, end_date)

    cardio_metrics = await analytics_service.get_cardio_metrics(db, user.id, start_dt, end_dt)
    strength_metrics = await analytics_service.get_strength_metrics(db, user.id, start_dt, end_dt)

    total_duration_hours = round(cardio_metrics.total_duration_hours, 2)
    zone2_hours = cardio_metrics.zone2_duration_hours
    zone2_pct = cardio_metrics.zone2_percentage
    total_miles = cardio_metrics.total_distance_miles
    total_volume_lbs = strength_metrics.total_volume_load_lbs
    working_sets = strength_metrics.effective_working_sets

    return UnifiedVolumeSummary(
        start_date=start_dt,
        end_date=end_dt,
        total_duration_hours=total_duration_hours,
        zone2_duration_hours=zone2_hours,
        zone2_percentage=zone2_pct,
        total_cardio_distance_miles=total_miles,
        total_strength_volume_lbs=total_volume_lbs,
        effective_working_sets=working_sets,
        cardio=cardio_metrics,
        strength=strength_metrics,
    )


@router.get("/prs", response_model=list[PersonalRecordItem])
async def get_personal_records(
    window: Optional[WindowPreset] = Query(default=WindowPreset.ALL_TIME),
    discipline: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve personal records and peak performances across rolling time windows."""
    user = await get_or_create_default_user(db)
    start_dt, end_dt = None, None
    if start_date and end_date:
        start_dt, end_dt = analytics_service.resolve_date_window(None, start_date, end_date)

    prs = await pr_detector.get_all_prs(
        db, user.id, window=window, start_time=start_dt, end_time=end_dt
    )

    if discipline:
        prs = [p for p in prs if p.discipline == discipline]

    return prs
