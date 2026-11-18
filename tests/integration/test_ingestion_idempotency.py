"""Integration test verifying sync idempotency produces zero duplicate workouts."""

import json
from pathlib import Path
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.polar import PolarAdapter
from src.models import WorkoutSession
from src.services.ingestion import ingest_workout


@pytest.mark.asyncio
async def test_repeated_sync_produces_zero_duplicates(db_session: AsyncSession, sample_user):
    user, hr_profile = sample_user
    fixture_path = Path(__file__).parent.parent / "fixtures" / "polar_samples.json"
    with open(fixture_path) as f:
        data = json.load(f)

    adapter = PolarAdapter()
    exercise = data["exercises"][0]
    samples = data["samples"]

    normalized = adapter.normalize_polar_exercise(exercise, samples)

    # First sync run
    w1, is_created1 = await ingest_workout(db_session, user.id, normalized, hr_profile)
    await db_session.commit()
    assert is_created1 is True

    # Run sync 4 more times with identical external data
    for _ in range(4):
        w, is_created = await ingest_workout(db_session, user.id, normalized, hr_profile)
        await db_session.commit()
        assert is_created is False
        assert w.id == w1.id

    # Verify exactly 1 workout in database
    count_q = select(func.count()).select_from(WorkoutSession)
    res = await db_session.execute(count_q)
    total_workouts = res.scalar()
    assert total_workouts == 1
