"""Workout ingestion service coordinator for persisting normalized workouts atomically."""

from datetime import timedelta
import uuid
from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.base import NormalizedWorkout
from src.models.base import utc_now
from src.models.telemetry import GPSRoutePoint, HeartRateSample, WorkoutSplit
from src.models.user import UserHeartRateProfile
from src.models.workout import WorkoutSession
from src.services.zone_calculator import calculate_zone_durations


async def _bulk_add_hr_samples(
    session: AsyncSession,
    workout_id: uuid.UUID,
    normalized: NormalizedWorkout,
) -> None:
    if not normalized.heart_rate_samples:
        return
    rows = [
        {
            "workout_id": workout_id,
            "timestamp_utc": normalized.start_time_utc + timedelta(seconds=sample.elapsed_sec),
            "elapsed_sec": sample.elapsed_sec,
            "bpm": sample.bpm,
        }
        for sample in normalized.heart_rate_samples
    ]
    await session.execute(insert(HeartRateSample), rows)


async def _bulk_add_gps_points(
    session: AsyncSession,
    workout_id: uuid.UUID,
    normalized: NormalizedWorkout,
) -> None:
    if not normalized.gps_route_points:
        return
    rows = [
        {
            "workout_id": workout_id,
            "timestamp_utc": normalized.start_time_utc + timedelta(seconds=pt.elapsed_sec),
            "elapsed_sec": pt.elapsed_sec,
            "latitude": pt.latitude,
            "longitude": pt.longitude,
            "altitude_m": pt.altitude_m,
        }
        for pt in normalized.gps_route_points
    ]
    await session.execute(insert(GPSRoutePoint), rows)


async def _bulk_add_splits(
    session: AsyncSession,
    workout_id: uuid.UUID,
    normalized: NormalizedWorkout,
) -> None:
    if not normalized.splits:
        return
    rows = [
        {
            "id": uuid.uuid4(),
            "workout_id": workout_id,
            "split_index": sp.split_index,
            "split_type": sp.split_type,
            "distance_m": sp.distance_m,
            "duration_sec": sp.duration_sec,
            "avg_pace_sec_per_km": sp.avg_pace_sec_per_km,
            "avg_power_watts": sp.avg_power_watts,
            "avg_cadence_spm": sp.avg_cadence_spm,
            "avg_heart_rate": sp.avg_heart_rate,
            "avg_split_sec_per_500m": sp.avg_split_sec_per_500m,
        }
        for sp in normalized.splits
    ]
    await session.execute(insert(WorkoutSplit), rows)


async def ingest_workout(
    session: AsyncSession,
    user_id: uuid.UUID,
    normalized: NormalizedWorkout,
    hr_profile: UserHeartRateProfile | None = None,
) -> tuple[WorkoutSession, bool]:
    """Persist or update a normalized workout session with its telemetry.

    Enforces idempotency using (provider, external_id), preserves local user_notes,
    preserves computed HR zones on metadata-only re-syncs without HR samples, and
    uses PostgreSQL ON CONFLICT upserts + bulk telemetry inserts.
    Returns (WorkoutSession, is_created).
    """
    has_hr = bool(normalized.heart_rate_samples)
    zone_durations = calculate_zone_durations(normalized.heart_rate_samples, hr_profile) if has_hr else None

    existing_q = select(WorkoutSession).where(
        WorkoutSession.provider == normalized.provider,
        WorkoutSession.external_id == normalized.external_id,
    )
    existing_workout = (await session.execute(existing_q)).scalar_one_or_none()
    dialect = session.bind.dialect.name if session.bind is not None else "sqlite"

    if existing_workout is None and dialect == "postgresql":
        # Concurrency-safe PostgreSQL ON CONFLICT DO UPDATE upsert
        now = utc_now()
        new_id = uuid.uuid4()
        insert_vals = {
            "id": new_id,
            "user_id": user_id,
            "provider": normalized.provider,
            "external_id": normalized.external_id,
            "discipline": normalized.discipline,
            "title": normalized.title,
            "start_time_utc": normalized.start_time_utc,
            "local_timezone": normalized.local_timezone,
            "total_duration_sec": normalized.total_duration_sec,
            "active_duration_sec": normalized.active_duration_sec,
            "total_distance_m": normalized.total_distance_m,
            "total_calories": normalized.total_calories,
            "avg_heart_rate": normalized.avg_heart_rate,
            "max_heart_rate": normalized.max_heart_rate,
            "zone1_duration_sec": zone_durations.zone1_sec if zone_durations else 0.0,
            "zone2_duration_sec": zone_durations.zone2_sec if zone_durations else 0.0,
            "zone3_duration_sec": zone_durations.zone3_sec if zone_durations else 0.0,
            "zone4_duration_sec": zone_durations.zone4_sec if zone_durations else 0.0,
            "zone5_duration_sec": zone_durations.zone5_sec if zone_durations else 0.0,
            "avg_pace_sec_per_km": normalized.avg_pace_sec_per_km,
            "elevation_gain_m": normalized.elevation_gain_m,
            "elevation_loss_m": normalized.elevation_loss_m,
            "total_strokes": normalized.total_strokes,
            "avg_cadence_spm": normalized.avg_cadence_spm,
            "avg_power_watts": normalized.avg_power_watts,
            "avg_split_sec_per_500m": normalized.avg_split_sec_per_500m,
            "avg_drag_factor": normalized.avg_drag_factor,
            "status": "active",
            "is_demo": False,
            "raw_summary": normalized.raw_summary,
            "created_at": now,
            "updated_at": now,
        }
        update_vals = {
            "discipline": normalized.discipline,
            "title": normalized.title,
            "start_time_utc": normalized.start_time_utc,
            "local_timezone": normalized.local_timezone,
            "total_duration_sec": normalized.total_duration_sec,
            "active_duration_sec": normalized.active_duration_sec,
            "total_distance_m": normalized.total_distance_m,
            "total_calories": normalized.total_calories,
            "avg_heart_rate": normalized.avg_heart_rate,
            "max_heart_rate": normalized.max_heart_rate,
            "avg_pace_sec_per_km": normalized.avg_pace_sec_per_km,
            "elevation_gain_m": normalized.elevation_gain_m,
            "elevation_loss_m": normalized.elevation_loss_m,
            "total_strokes": normalized.total_strokes,
            "avg_cadence_spm": normalized.avg_cadence_spm,
            "avg_power_watts": normalized.avg_power_watts,
            "avg_split_sec_per_500m": normalized.avg_split_sec_per_500m,
            "avg_drag_factor": normalized.avg_drag_factor,
            "raw_summary": normalized.raw_summary,
            "updated_at": now,
        }
        if zone_durations is not None:
            update_vals.update({
                "zone1_duration_sec": zone_durations.zone1_sec,
                "zone2_duration_sec": zone_durations.zone2_sec,
                "zone3_duration_sec": zone_durations.zone3_sec,
                "zone4_duration_sec": zone_durations.zone4_sec,
                "zone5_duration_sec": zone_durations.zone5_sec,
            })
        stmt = (
            pg_insert(WorkoutSession)
            .values(**insert_vals)
            .on_conflict_do_update(
                constraint="uq_provider_external_id",
                set_=update_vals,
            )
            .returning(WorkoutSession.id)
        )
        returned_id = (await session.execute(stmt)).scalar_one()
        is_created = returned_id == new_id

        if normalized.heart_rate_samples:
            if not is_created:
                await session.execute(delete(HeartRateSample).where(HeartRateSample.workout_id == returned_id))
            await _bulk_add_hr_samples(session, returned_id, normalized)
        if normalized.gps_route_points:
            if not is_created:
                await session.execute(delete(GPSRoutePoint).where(GPSRoutePoint.workout_id == returned_id))
            await _bulk_add_gps_points(session, returned_id, normalized)
        if normalized.splits:
            if not is_created:
                await session.execute(delete(WorkoutSplit).where(WorkoutSplit.workout_id == returned_id))
            await _bulk_add_splits(session, returned_id, normalized)

        workout = (await session.execute(select(WorkoutSession).where(WorkoutSession.id == returned_id))).scalar_one()
        return workout, is_created

    if existing_workout is not None:
        # Soft-sync update: preserve user_notes and preserve existing HR zones if no new HR samples arrived
        existing_workout.discipline = normalized.discipline
        existing_workout.title = normalized.title
        existing_workout.start_time_utc = normalized.start_time_utc
        existing_workout.local_timezone = normalized.local_timezone
        existing_workout.total_duration_sec = normalized.total_duration_sec
        existing_workout.active_duration_sec = normalized.active_duration_sec
        existing_workout.total_distance_m = normalized.total_distance_m
        existing_workout.total_calories = normalized.total_calories
        existing_workout.avg_heart_rate = normalized.avg_heart_rate
        existing_workout.max_heart_rate = normalized.max_heart_rate
        if zone_durations is not None:
            existing_workout.zone1_duration_sec = zone_durations.zone1_sec
            existing_workout.zone2_duration_sec = zone_durations.zone2_sec
            existing_workout.zone3_duration_sec = zone_durations.zone3_sec
            existing_workout.zone4_duration_sec = zone_durations.zone4_sec
            existing_workout.zone5_duration_sec = zone_durations.zone5_sec
        existing_workout.avg_pace_sec_per_km = normalized.avg_pace_sec_per_km
        existing_workout.elevation_gain_m = normalized.elevation_gain_m
        existing_workout.elevation_loss_m = normalized.elevation_loss_m
        existing_workout.total_strokes = normalized.total_strokes
        existing_workout.avg_cadence_spm = normalized.avg_cadence_spm
        existing_workout.avg_power_watts = normalized.avg_power_watts
        existing_workout.avg_split_sec_per_500m = normalized.avg_split_sec_per_500m
        existing_workout.avg_drag_factor = normalized.avg_drag_factor
        existing_workout.raw_summary = normalized.raw_summary

        if normalized.heart_rate_samples:
            await session.execute(delete(HeartRateSample).where(HeartRateSample.workout_id == existing_workout.id))
            await _bulk_add_hr_samples(session, existing_workout.id, normalized)

        if normalized.gps_route_points:
            await session.execute(delete(GPSRoutePoint).where(GPSRoutePoint.workout_id == existing_workout.id))
            await _bulk_add_gps_points(session, existing_workout.id, normalized)

        if normalized.splits:
            await session.execute(delete(WorkoutSplit).where(WorkoutSplit.workout_id == existing_workout.id))
            await _bulk_add_splits(session, existing_workout.id, normalized)

        return existing_workout, False

    workout_id = uuid.uuid4()
    workout = WorkoutSession(
        id=workout_id,
        user_id=user_id,
        provider=normalized.provider,
        external_id=normalized.external_id,
        discipline=normalized.discipline,
        title=normalized.title,
        start_time_utc=normalized.start_time_utc,
        local_timezone=normalized.local_timezone,
        total_duration_sec=normalized.total_duration_sec,
        active_duration_sec=normalized.active_duration_sec,
        total_distance_m=normalized.total_distance_m,
        total_calories=normalized.total_calories,
        avg_heart_rate=normalized.avg_heart_rate,
        max_heart_rate=normalized.max_heart_rate,
        zone1_duration_sec=zone_durations.zone1_sec if zone_durations else 0.0,
        zone2_duration_sec=zone_durations.zone2_sec if zone_durations else 0.0,
        zone3_duration_sec=zone_durations.zone3_sec if zone_durations else 0.0,
        zone4_duration_sec=zone_durations.zone4_sec if zone_durations else 0.0,
        zone5_duration_sec=zone_durations.zone5_sec if zone_durations else 0.0,
        avg_pace_sec_per_km=normalized.avg_pace_sec_per_km,
        elevation_gain_m=normalized.elevation_gain_m,
        elevation_loss_m=normalized.elevation_loss_m,
        total_strokes=normalized.total_strokes,
        avg_cadence_spm=normalized.avg_cadence_spm,
        avg_power_watts=normalized.avg_power_watts,
        avg_split_sec_per_500m=normalized.avg_split_sec_per_500m,
        avg_drag_factor=normalized.avg_drag_factor,
        status="active",
        raw_summary=normalized.raw_summary,
    )
    session.add(workout)
    await session.flush()

    await _bulk_add_hr_samples(session, workout_id, normalized)
    await _bulk_add_gps_points(session, workout_id, normalized)
    await _bulk_add_splits(session, workout_id, normalized)

    return workout, True
