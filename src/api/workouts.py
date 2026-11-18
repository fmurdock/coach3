"""API endpoints for querying workout sessions and telemetry streams."""

from datetime import date, datetime, time, timezone
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models.workout import WorkoutSession
from src.schemas.workout import (
    WorkoutSessionDetailResponse,
    WorkoutSessionResponse,
    WorkoutTelemetryResponse,
)

router = APIRouter(prefix="/api/v1/workouts", tags=["Workouts"])


@router.get("", response_model=list[WorkoutSessionResponse])
async def list_workouts(
    discipline: Literal["outdoor_run", "indoor_row", "erg_bike"] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(WorkoutSession).order_by(WorkoutSession.start_time_utc.desc())

    if discipline:
        query = query.where(WorkoutSession.discipline == discipline)
    if start_date:
        dt_start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        query = query.where(WorkoutSession.start_time_utc >= dt_start)
    if end_date:
        dt_end = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        query = query.where(WorkoutSession.start_time_utc <= dt_end)

    query = query.limit(limit)
    res = await db.execute(query)
    return res.scalars().all()


@router.get("/{workout_id}", response_model=WorkoutSessionDetailResponse)
async def get_workout(workout_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    query = select(WorkoutSession).where(WorkoutSession.id == workout_id)
    res = await db.execute(query)
    workout = res.scalar_one_or_none()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return workout


@router.get("/{workout_id}/telemetry", response_model=WorkoutTelemetryResponse)
async def get_workout_telemetry(workout_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    query = (
        select(WorkoutSession)
        .options(
            selectinload(WorkoutSession.heart_rate_samples),
            selectinload(WorkoutSession.gps_route_points),
            selectinload(WorkoutSession.splits),
        )
        .where(WorkoutSession.id == workout_id)
    )
    res = await db.execute(query)
    workout = res.scalar_one_or_none()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    return WorkoutTelemetryResponse(
        workout_id=workout.id,
        heart_rate_samples=workout.heart_rate_samples,
        gps_route_points=workout.gps_route_points,
        splits=workout.splits,
    )
