"""API endpoints for managing User Heart Rate Profile and zones."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.adapters.base import NormalizedHeartRateSample
from src.api.integrations import get_or_create_default_user
from src.core.database import get_db
from src.models.user import UserHeartRateProfile
from src.models.workout import WorkoutSession
from src.schemas.profile import HeartRateProfileRequest, HeartRateProfileResponse
from src.services.zone_calculator import calculate_zone_durations

router = APIRouter(prefix="/api/v1/profile/heart-rate", tags=["Profile"])


@router.get("", response_model=HeartRateProfileResponse)
async def get_heart_rate_profile(db: AsyncSession = Depends(get_db)):
    user = await get_or_create_default_user(db)
    q = select(UserHeartRateProfile).where(UserHeartRateProfile.user_id == user.id)
    res = await db.execute(q)
    profile = res.scalar_one_or_none()

    if not profile:
        # Default profile initialized from 185 bpm Max HR (editable in Settings, never hardcoded in analytics)
        default_max_hr = 185
        profile = UserHeartRateProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            resting_hr=50,
            max_hr=default_max_hr,
            zone1_min=round(default_max_hr * 0.50),
            zone1_max=round(default_max_hr * 0.60),
            zone2_min=round(default_max_hr * 0.60),
            zone2_max=round(default_max_hr * 0.70),
            zone3_min=round(default_max_hr * 0.70),
            zone3_max=round(default_max_hr * 0.80),
            zone4_min=round(default_max_hr * 0.80),
            zone4_max=round(default_max_hr * 0.90),
            zone5_min=round(default_max_hr * 0.90),
            zone5_max=default_max_hr,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return profile


@router.put("", response_model=HeartRateProfileResponse)
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

    # Recompute zone durations across existing workouts with recorded HR samples
    w_res = await db.execute(
        select(WorkoutSession)
        .options(selectinload(WorkoutSession.heart_rate_samples))
        .where(WorkoutSession.user_id == user.id)
    )
    for w in w_res.scalars().all():
        if w.heart_rate_samples:
            norm_samples = [
                NormalizedHeartRateSample(
                    elapsed_sec=s.elapsed_sec,
                    bpm=s.bpm,
                    timestamp_utc=s.timestamp_utc,
                )
                for s in w.heart_rate_samples
            ]
            zd = calculate_zone_durations(norm_samples, profile)
            w.zone1_duration_sec = zd.zone1_sec
            w.zone2_duration_sec = zd.zone2_sec
            w.zone3_duration_sec = zd.zone3_sec
            w.zone4_duration_sec = zd.zone4_sec
            w.zone5_duration_sec = zd.zone5_sec

    await db.commit()
    await db.refresh(profile)
    return profile
