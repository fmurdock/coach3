"""Admin endpoints for local environment setup, demo data seeding, and test resets."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas.config import ResetResult, SeedResult
from src.services.seed_service import SeedService

router = APIRouter(prefix="/api/v1/admin", tags=["Admin & Testing"])


@router.post("/demo/seed", response_model=SeedResult, status_code=status.HTTP_201_CREATED)
async def seed_demo_data(db: AsyncSession = Depends(get_db)):
    """Seeds multi-modal workout sessions (running, rowing, bike, strength) with is_demo=True."""
    w_count, s_count = await SeedService.seed_sample_workouts(db)
    msg = (
        f"Seeded {w_count} workouts and {s_count} strength sets."
        if (w_count or s_count)
        else "Demo workouts already exist in database."
    )
    return SeedResult(
        status="success",
        workouts_created=w_count,
        strength_sets_created=s_count,
        message=msg,
    )


@router.delete("/demo", response_model=ResetResult)
async def reset_demo_data(db: AsyncSession = Depends(get_db)):
    """Purges only synthetic records where is_demo=True, preserving authentic athlete data."""
    deleted_count = await SeedService.purge_demo_data(db)
    return ResetResult(
        status="success",
        workouts_deleted=deleted_count,
        message=f"Purged {deleted_count} demo workout records.",
    )
