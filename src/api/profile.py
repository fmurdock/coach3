"""API endpoints for managing User Heart Rate Profile and zones."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.integrations import get_or_create_default_user
from src.core.database import get_db
from src.models.user import UserHeartRateProfile
from src.schemas.profile import HeartRateProfileRequest, HeartRateProfileResponse

router = APIRouter(prefix="/api/v1/profile/heart-rate", tags=["Profile"])


@router.get("", response_model=HeartRateProfileResponse)
async def get_heart_rate_profile(db: AsyncSession = Depends(get_db)):
    user = await get_or_create_default_user(db)
    q = select(UserHeartRateProfile).where(UserHeartRateProfile.user_id == user.id)
    res = await db.execute(q)
    profile = res.scalar_one_or_none()

    if not profile:
        # Default profile
        profile = UserHeartRateProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            resting_hr=50,
            max_hr=190,
            zone1_min=95,
            zone1_max=114,
            zone2_min=114,
            zone2_max=133,
            zone3_min=133,
            zone3_max=152,
            zone4_min=152,
            zone4_max=171,
            zone5_min=171,
            zone5_max=190,
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

    await db.commit()
    await db.refresh(profile)
    return profile
