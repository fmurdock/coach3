"""API endpoints for querying, updating, and uploading telemetry for workout sessions."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, exists, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.adapters.polar import compute_elevation_from_points, parse_gpx_points
from src.core.database import get_db
from src.core.deps import get_or_create_default_user
from src.models.strength_set import StrengthSet
from src.models.telemetry import GPSRoutePoint, HeartRateSample, WorkoutSplit
from src.models.workout import WorkoutSession
from src.schemas.analytics import WindowPreset
from src.schemas.workout import (
    GPSRoutePointSchema,
    GPXUploadRequest,
    HeartRateSampleSchema,
    WorkoutDetailTelemetry,
    WorkoutSessionDetailResponse,
    WorkoutSplitSchema,
    WorkoutTableRow,
    WorkoutTelemetryResponse,
    WorkoutUpdateRequest,
)
from src.services.analytics_service import AnalyticsService, _resolve_tz

router = APIRouter(prefix="/api/v1/workouts", tags=["Workouts"])
analytics_service = AnalyticsService()


def _format_primary_metric(w: WorkoutSession, working_set_count: int = 0) -> str:
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
        return f"{working_set_count} working sets"
    return f"{int(w.total_duration_sec // 60)} mins"


@router.get("", response_model=list[WorkoutTableRow])
async def list_workouts(
    response: Response,
    discipline: Literal["outdoor_run", "indoor_row", "erg_bike", "strength"] | None = None,
    window: WindowPreset | None = Query(default=None),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List active athlete workouts without hydrating HR sample rows (SQL EXISTS/COUNT subqueries)."""
    user = await get_or_create_default_user(db)
    tz_name = user.timezone or "UTC"
    tz = _resolve_tz(tz_name)

    filters = [
        WorkoutSession.user_id == user.id,
        WorkoutSession.status == "active",
    ]
    if discipline:
        filters.append(WorkoutSession.discipline == discipline)

    if window is not None and not (start_date and end_date):
        dt_start, dt_end = analytics_service.resolve_date_window(window, tz_name=tz_name)
        filters.append(WorkoutSession.start_time_utc >= dt_start)
        filters.append(WorkoutSession.start_time_utc <= dt_end)
    else:
        if start_date:
            dt_start = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
            filters.append(WorkoutSession.start_time_utc >= dt_start)
        if end_date:
            dt_end = datetime.combine(end_date, time.max, tzinfo=tz).astimezone(timezone.utc)
            filters.append(WorkoutSession.start_time_utc <= dt_end)

    total_count = int(
        (await db.execute(select(func.count(WorkoutSession.id)).where(*filters))).scalar() or 0
    )
    response.headers["X-Total-Count"] = str(total_count)

    # Lightweight correlated subqueries — zero HR/split/set rows loaded into Python!
    has_hr_subq = exists(
        select(1).where(HeartRateSample.workout_id == WorkoutSession.id)
    ).label("has_hr_samples")

    work_splits_subq = (
        select(func.count(WorkoutSplit.id))
        .where(
            WorkoutSplit.workout_id == WorkoutSession.id,
            WorkoutSplit.split_type.in_(("interval", "work")),
        )
        .correlate(WorkoutSession)
        .scalar_subquery()
        .label("work_split_count")
    )

    working_sets_subq = (
        select(func.count(StrengthSet.id))
        .where(
            StrengthSet.workout_session_id == WorkoutSession.id,
            StrengthSet.is_warmup.is_(False),
        )
        .correlate(WorkoutSession)
        .scalar_subquery()
        .label("working_set_count")
    )

    query = (
        select(WorkoutSession, has_hr_subq, work_splits_subq, working_sets_subq)
        .where(*filters)
        .order_by(WorkoutSession.start_time_utc.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(query)

    rows: list[WorkoutTableRow] = []
    for w, has_hr, work_splits, working_sets in res.all():
        has_tel = bool(has_hr) or (w.discipline in ("outdoor_run", "indoor_row", "erg_bike"))
        is_int = int(work_splits or 0) >= 2
        ws_count = int(working_sets or 0)
        rows.append(
            WorkoutTableRow(
                id=w.id,
                discipline=w.discipline,
                title=w.title,
                start_time_utc=w.start_time_utc,
                duration_sec=w.total_duration_sec,
                distance_m=w.total_distance_m,
                avg_heart_rate=w.avg_heart_rate,
                max_heart_rate=w.max_heart_rate,
                primary_metric_label=_format_primary_metric(w, working_set_count=ws_count),
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
        )
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


@router.patch("/{workout_id}", response_model=WorkoutSessionDetailResponse)
async def update_workout(
    workout_id: uuid.UUID,
    payload: WorkoutUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Edit title and/or user_notes on a workout session."""
    user = await get_or_create_default_user(db)
    res = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.id == workout_id,
            WorkoutSession.user_id == user.id,
        )
    )
    workout = res.scalar_one_or_none()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    if payload.title is not None:
        workout.title = payload.title.strip()
    if payload.user_notes is not None:
        workout.user_notes = payload.user_notes
    await db.flush()
    await db.refresh(workout)
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
        heart_rate_samples=[HeartRateSampleSchema.model_validate(s) for s in workout.heart_rate_samples],
        gps_route_points=[GPSRoutePointSchema.model_validate(p) for p in workout.gps_route_points],
        splits=[WorkoutSplitSchema.model_validate(sp) for sp in workout.splits],
    )


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
    rows = [
        {
            "workout_id": workout_id,
            "timestamp_utc": workout.start_time_utc + timedelta(seconds=pt["elapsed_sec"]),
            "elapsed_sec": pt["elapsed_sec"],
            "latitude": pt["latitude"],
            "longitude": pt["longitude"],
            "altitude_m": pt.get("altitude"),
        }
        for pt in parsed
    ]
    if rows:
        await db.execute(insert(GPSRoutePoint), rows)

    if workout.elevation_gain_m is None or workout.elevation_loss_m is None:
        gain, loss = compute_elevation_from_points(parsed)
        if workout.elevation_gain_m is None and gain is not None:
            workout.elevation_gain_m = gain
        if workout.elevation_loss_m is None and loss is not None:
            workout.elevation_loss_m = loss

    await db.flush()
    detail = await analytics_service.get_workout_detail_telemetry(db, workout_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Workout not found")
    return detail
