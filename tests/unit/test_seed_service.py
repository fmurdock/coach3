"""Unit tests for SeedService demo data creation and isolated purging."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import WorkoutSession
from src.services.seed_service import SeedService


@pytest.mark.asyncio
async def test_seed_and_purge_demo_workouts(db_session: AsyncSession):
    # 1. Seed demo workouts
    w_count, s_count = await SeedService.seed_sample_workouts(db_session)
    assert w_count == 5
    assert s_count == 7

    # Verify workouts created with is_demo=True
    q = select(WorkoutSession).where(WorkoutSession.is_demo == True)
    res = await db_session.execute(q)
    demos = res.scalars().all()
    assert len(demos) == 5

    # 2. Add an authentic user workout (is_demo=False)
    user = await SeedService.ensure_default_athlete_and_philosophy(db_session)
    import uuid
    from datetime import datetime, timezone
    real_w = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="manual",
        external_id="real_workout_123",
        discipline="outdoor_run",
        title="Real Sunday Run",
        start_time_utc=datetime.now(timezone.utc),
        total_duration_sec=1800.0,
        active_duration_sec=1800.0,
        total_distance_m=5000.0,
        is_demo=False,
        status="active",
    )
    db_session.add(real_w)
    await db_session.commit()

    # 3. Purge demo data
    deleted = await SeedService.purge_demo_data(db_session)
    assert deleted == 5

    # 4. Verify authentic workout was preserved
    q_real = select(WorkoutSession).where(WorkoutSession.is_demo == False)
    res_real = await db_session.execute(q_real)
    reals = res_real.scalars().all()
    assert len(reals) == 1
    assert reals[0].title == "Real Sunday Run"
