"""API endpoints for managing User Heart Rate Profile, zones, and athlete preferences."""

from collections import defaultdict
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.base import NormalizedHeartRateSample
from src.core.database import get_db
from src.core.deps import get_or_create_default_hr_profile, get_or_create_default_user
from src.models.telemetry import HeartRateSample
from src.models.user import UserHeartRateProfile
from src.models.workout import WorkoutSession
from src.schemas.profile import (
    AthletePreferences,
    HeartRateProfileRequest,
    HeartRateProfileResponse,
)
from src.services.zone_calculator import calculate_zone_durations

router = APIRouter(prefix="/api/v1/profile", tags=["Profile"])

RECALC_BATCH_SIZE = 25


@router.get("/heart-rate", response_model=HeartRateProfileResponse)
async def get_heart_rate_profile(db: AsyncSession = Depends(get_db)):
    user = await get_or_create_default_user(db)
    profile = await get_or_create_default_hr_profile(db, user.id)
    await db.flush()
    return profile


@router.put("/heart-rate", response_model=HeartRateProfileResponse)
async def update_heart_rate_profile(
    payload: HeartRateProfileRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await get_or_create_default_user(db)
    q = select(UserHeartRateProfile).where(UserHeartRateProfile.user_id == user.id)
    res = await db.execute(q)
    profile = res.scalar_one_or_none()

    if not profile:
        profile = UserHeartRateProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            **payload.model_dump(),
        )
        db.add(profile)
    else:
        for k, v in payload.model_dump().items():
            setattr(profile, k, v)
    await db.flush()

    # Recompute zone durations in bounded batches of 25 workouts to avoid OOM on multi-year histories
    id_res = await db.execute(
        select(WorkoutSession.id)
        .where(WorkoutSession.user_id == user.id)
        .order_by(WorkoutSession.start_time_utc.asc())
    )
    workout_ids = list(id_res.scalars().all())

    for start_idx in range(0, len(workout_ids), RECALC_BATCH_SIZE):
        batch_ids = workout_ids[start_idx : start_idx + RECALC_BATCH_SIZE]

        samples_res = await db.execute(
            select(
                HeartRateSample.workout_id,
                HeartRateSample.elapsed_sec,
                HeartRateSample.bpm,
                HeartRateSample.timestamp_utc,
            )
            .where(HeartRateSample.workout_id.in_(batch_ids))
            .order_by(HeartRateSample.workout_id, HeartRateSample.elapsed_sec)
        )
        samples_by_workout: dict[uuid.UUID, list[NormalizedHeartRateSample]] = defaultdict(list)
        for wid, elapsed_sec, bpm, ts_utc in samples_res.all():
            samples_by_workout[wid].append(
                NormalizedHeartRateSample(
                    elapsed_sec=elapsed_sec,
                    bpm=bpm,
                    timestamp_utc=ts_utc,
                )
            )

        if not samples_by_workout:
            continue

        workouts_res = await db.execute(
            select(WorkoutSession).where(WorkoutSession.id.in_(list(samples_by_workout.keys())))
        )
        for w in workouts_res.scalars().all():
            norm_samples = samples_by_workout.get(w.id)
            if norm_samples:
                zd = calculate_zone_durations(norm_samples, profile)
                w.zone1_duration_sec = zd.zone1_sec
                w.zone2_duration_sec = zd.zone2_sec
                w.zone3_duration_sec = zd.zone3_sec
                w.zone4_duration_sec = zd.zone4_sec
                w.zone5_duration_sec = zd.zone5_sec
        await db.flush()

    return profile


@router.get("/preferences", response_model=AthletePreferences)
async def get_athlete_preferences(db: AsyncSession = Depends(get_db)):
    user = await get_or_create_default_user(db)
    return AthletePreferences(timezone=user.timezone or "UTC")


@router.put("/preferences", response_model=AthletePreferences)
async def update_athlete_preferences(
    payload: AthletePreferences,
    db: AsyncSession = Depends(get_db),
):
    user = await get_or_create_default_user(db)
    user.timezone = payload.timezone
    await db.flush()
    return AthletePreferences(timezone=user.timezone)
