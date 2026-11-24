"""API endpoints for querying workout sessions and telemetry streams."""

from datetime import date, datetime, time, timedelta, timezone
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.adapters.polar import compute_elevation_from_points, parse_gpx_points
from src.core.database import get_db
from src.models.telemetry import GPSRoutePoint
from src.models.workout import WorkoutSession
from src.schemas.workout import (
    WorkoutDetailTelemetry,
    WorkoutSessionDetailResponse,
    WorkoutSessionResponse,
    WorkoutTableRow,
    WorkoutTelemetryResponse,
)
from src.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/workouts", tags=["Workouts"])
analytics_service = AnalyticsService()


def _format_primary_metric(w: WorkoutSession) -> str:
    if w.discipline == "indoor_row":
        if w.avg_split_sec_per_500m:
            m = int(w.avg_split_sec_per_500m // 60)
            s = w.avg_split_sec_per_500m % 60
            return f"Split {m}:{s:04.1f}/500m"
        elif w.avg_power_watts:
            return f"{w.avg_power_watts:.0f}W avg"
        return f"{int(w.total_distance_m)}m rowed"
    elif w.discipline == "outdoor_run":
        dist_km = (w.total_distance_m or 0.0) / 1000.0
        if w.avg_pace_sec_per_km:
            m = int(w.avg_pace_sec_per_km // 60)
            s = int(w.avg_pace_sec_per_km % 60)
            return f"{dist_km:.2f} km @ {m}:{s:02d}/km"
        return f"{dist_km:.2f} km run"
    elif w.discipline == "erg_bike":
        dist_km = (w.total_distance_m or 0.0) / 1000.0
        if w.avg_power_watts:
            return f"{w.avg_power_watts:.0f}W · {dist_km:.1f} km"
        return f"{dist_km:.1f} km cycled"
    elif w.discipline == "strength":
        set_count = len(w.strength_sets) if w.strength_sets else 0
        return f"{set_count} working sets"
    return f"{int(w.total_duration_sec // 60)} mins"


@router.get("", response_model=list[WorkoutTableRow])
async def list_workouts(
    discipline: Literal["outdoor_run", "indoor_row", "erg_bike", "strength"] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(WorkoutSession)
        .options(
            selectinload(WorkoutSession.splits),
            selectinload(WorkoutSession.heart_rate_samples),
            selectinload(WorkoutSession.strength_sets),
        )
        .order_by(WorkoutSession.start_time_utc.desc())
    )

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
    workouts = res.scalars().all()

    rows = []
    for w in workouts:
        has_tel = (len(w.heart_rate_samples) > 0) or (w.discipline in ["outdoor_run", "indoor_row", "erg_bike"])
        is_int = sum(1 for s in w.splits if s.split_type in ("interval", "work")) >= 2
        row = WorkoutTableRow(
            id=w.id,
            discipline=w.discipline,
            title=w.title,
            start_time_utc=w.start_time_utc,
            duration_sec=w.total_duration_sec,
            distance_m=w.total_distance_m,
            avg_heart_rate=w.avg_heart_rate,
            max_heart_rate=w.max_heart_rate,
            primary_metric_label=_format_primary_metric(w),
            has_telemetry=has_tel,
            is_interval_workout=is_int,
            provider=w.provider,
            external_id=w.external_id,
            total_duration_sec=w.total_duration_sec,
            active_duration_sec=w.active_duration_sec,
            total_distance_m=w.total_distance_m,
            zone2_duration_sec=w.zone2_duration_sec,
            avg_pace_sec_per_km=w.avg_pace_sec_per_km,
            avg_power_watts=w.avg_power_watts,
            status=w.status,
        )
        rows.append(row)
    return rows


@router.get("/{workout_id}/detail", response_model=WorkoutDetailTelemetry)
async def get_workout_detail(workout_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    detail = await analytics_service.get_workout_detail_telemetry(db, workout_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Workout not found")
    return detail


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


class GPXUploadRequest(BaseModel):
    gpx_xml: str


@router.post("/{workout_id}/gpx", response_model=WorkoutDetailTelemetry)
async def upload_workout_gpx(
    workout_id: uuid.UUID,
    payload: GPXUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Attach or replace GPS route points on an existing workout from exported GPX XML."""
    res = await db.execute(select(WorkoutSession).where(WorkoutSession.id == workout_id))
    workout = res.scalar_one_or_none()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    parsed = parse_gpx_points(payload.gpx_xml, start_time_utc=workout.start_time_utc)
    if not parsed:
        raise HTTPException(status_code=400, detail="No valid <trkpt> coordinates found in GPX data")

    await db.execute(delete(GPSRoutePoint).where(GPSRoutePoint.workout_id == workout_id))
    for pt in parsed:
        db.add(
            GPSRoutePoint(
                workout_id=workout_id,
                timestamp_utc=workout.start_time_utc + timedelta(seconds=pt["elapsed_sec"]),
                elapsed_sec=pt["elapsed_sec"],
                latitude=pt["latitude"],
                longitude=pt["longitude"],
                altitude_m=pt.get("altitude"),
            )
        )

    if workout.elevation_gain_m is None or workout.elevation_loss_m is None:
        gain, loss = compute_elevation_from_points(parsed)
        if workout.elevation_gain_m is None and gain is not None:
            workout.elevation_gain_m = gain
        if workout.elevation_loss_m is None and loss is not None:
            workout.elevation_loss_m = loss

    await db.commit()
    detail = await analytics_service.get_workout_detail_telemetry(db, workout_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Workout not found")
    return detail
