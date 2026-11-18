"""Workout ingestion service coordinator for persisting normalized workouts atomically."""

from datetime import timedelta
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.base import NormalizedWorkout
from src.models.telemetry import GPSRoutePoint, HeartRateSample, WorkoutSplit
from src.models.user import UserHeartRateProfile
from src.models.workout import WorkoutSession
from src.services.zone_calculator import calculate_zone_durations


async def ingest_workout(
    session: AsyncSession,
    user_id: uuid.UUID,
    normalized: NormalizedWorkout,
    hr_profile: UserHeartRateProfile | None = None,
) -> tuple[WorkoutSession, bool]:
    """Persist or update a normalized workout session with its telemetry.
    
    Enforces idempotency using (provider, external_id).
    Returns a tuple of (WorkoutSession, is_created).
    """
    # 1. Compute Zone 1-5 durations locally from raw HR samples
    zone_durations = calculate_zone_durations(normalized.heart_rate_samples, hr_profile)

    # 2. Check for existing session
    query = select(WorkoutSession).where(
        WorkoutSession.provider == normalized.provider,
        WorkoutSession.external_id == normalized.external_id,
    )
    result = await session.execute(query)
    existing_workout = result.scalar_one_or_none()

    if existing_workout:
        # Soft-sync update: update telemetry & metrics, preserve user notes
        existing_workout.title = normalized.title
        existing_workout.total_duration_sec = normalized.total_duration_sec
        existing_workout.active_duration_sec = normalized.active_duration_sec
        existing_workout.total_distance_m = normalized.total_distance_m
        existing_workout.total_calories = normalized.total_calories
        existing_workout.avg_heart_rate = normalized.avg_heart_rate
        existing_workout.max_heart_rate = normalized.max_heart_rate
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
        return existing_workout, False

    # 3. Create new WorkoutSession
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
        zone1_duration_sec=zone_durations.zone1_sec,
        zone2_duration_sec=zone_durations.zone2_sec,
        zone3_duration_sec=zone_durations.zone3_sec,
        zone4_duration_sec=zone_durations.zone4_sec,
        zone5_duration_sec=zone_durations.zone5_sec,
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

    # 4. Attach HeartRateSamples
    for sample in normalized.heart_rate_samples:
        hr_record = HeartRateSample(
            workout_id=workout_id,
            timestamp_utc=normalized.start_time_utc + timedelta(seconds=sample.elapsed_sec),
            elapsed_sec=sample.elapsed_sec,
            bpm=sample.bpm,
        )
        session.add(hr_record)

    # 5. Attach GPSRoutePoints
    for pt in normalized.gps_route_points:
        gps_record = GPSRoutePoint(
            workout_id=workout_id,
            timestamp_utc=normalized.start_time_utc + timedelta(seconds=pt.elapsed_sec),
            elapsed_sec=pt.elapsed_sec,
            latitude=pt.latitude,
            longitude=pt.longitude,
            altitude_m=pt.altitude_m,
        )
        session.add(gps_record)

    # 6. Attach Splits
    for sp in normalized.splits:
        split_record = WorkoutSplit(
            id=uuid.uuid4(),
            workout_id=workout_id,
            split_index=sp.split_index,
            split_type=sp.split_type,
            distance_m=sp.distance_m,
            duration_sec=sp.duration_sec,
            avg_pace_sec_per_km=sp.avg_pace_sec_per_km,
            avg_power_watts=sp.avg_power_watts,
            avg_cadence_spm=sp.avg_cadence_spm,
            avg_heart_rate=sp.avg_heart_rate,
            avg_split_sec_per_500m=sp.avg_split_sec_per_500m,
        )
        session.add(split_record)

    return workout, True
