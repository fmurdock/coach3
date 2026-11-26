"""Shared single-athlete database dependency helpers (race-safe initialization)."""

import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User, UserHeartRateProfile

DEFAULT_ATHLETE_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
DEFAULT_MAX_HR = 185
DEFAULT_RESTING_HR = 50

_user_init_lock = asyncio.Lock()


async def get_or_create_default_user(db: AsyncSession) -> User:
    """Retrieve or race-safely initialize the single self-hosted athlete record.

    Uses flush() only so the caller's request unit-of-work owns commit/rollback.
    """
    res = await db.execute(select(User).order_by(User.created_at.asc()).limit(1))
    user = res.scalars().first()
    if user is not None:
        return user

    async with _user_init_lock:
        res = await db.execute(select(User).order_by(User.created_at.asc()).limit(1))
        user = res.scalars().first()
        if user is not None:
            return user

        user = User(id=DEFAULT_ATHLETE_ID, timezone="UTC")
        db.add(user)
        await db.flush()
        return user


async def get_or_create_default_hr_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    max_hr: int = DEFAULT_MAX_HR,
    resting_hr: int = DEFAULT_RESTING_HR,
) -> UserHeartRateProfile:
    """Retrieve or initialize a consistent default Heart Rate Zones Profile (185 bpm Max HR)."""
    res = await db.execute(
        select(UserHeartRateProfile).where(UserHeartRateProfile.user_id == user_id)
    )
    profile = res.scalar_one_or_none()
    if profile is not None:
        return profile

    profile = UserHeartRateProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        resting_hr=resting_hr,
        max_hr=max_hr,
        zone1_min=round(max_hr * 0.50),
        zone1_max=round(max_hr * 0.60),
        zone2_min=round(max_hr * 0.60),
        zone2_max=round(max_hr * 0.70),
        zone3_min=round(max_hr * 0.70),
        zone3_max=round(max_hr * 0.80),
        zone4_min=round(max_hr * 0.80),
        zone4_max=round(max_hr * 0.90),
        zone5_min=round(max_hr * 0.90),
        zone5_max=max_hr,
    )
    db.add(profile)
    await db.flush()
    return profile

