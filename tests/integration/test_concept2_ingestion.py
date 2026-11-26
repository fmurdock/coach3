"""Integration tests for Concept2 rower and bike erg workout ingestion."""

import json
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.concept2 import Concept2Adapter
from src.models import WorkoutSplit
from src.services.ingestion import ingest_workout


@pytest.mark.asyncio
async def test_end_to_end_concept2_rower_ingestion(db_session: AsyncSession, sample_user):
    user, hr_profile = sample_user
    fixture_path = Path(__file__).parent.parent / "fixtures" / "concept2_samples.json"
    with open(fixture_path) as f:
        data = json.load(f)

    adapter = Concept2Adapter()
    rower_data = data["rower_workout"]
    normalized = adapter.normalize_concept2_workout(rower_data)

    workout, is_created = await ingest_workout(
        session=db_session,
        user_id=user.id,
        normalized=normalized,
        hr_profile=hr_profile,
    )
    await db_session.commit()

    assert is_created is True
    assert workout.provider == "concept2"
    assert workout.external_id == "11223344"
    assert workout.discipline == "indoor_row"
    assert workout.total_distance_m == 5000.0
    assert workout.avg_split_sec_per_500m == 120.0
    assert workout.avg_power_watts == 202.0
    assert workout.avg_drag_factor == 125

    # Verify splits saved in database
    q_sp = select(WorkoutSplit).where(WorkoutSplit.workout_id == workout.id).order_by(WorkoutSplit.split_index)
    res_sp = await db_session.execute(q_sp)
    splits = res_sp.scalars().all()
    assert len(splits) == 5
    assert splits[0].split_index == 1
    assert splits[0].distance_m == 1000.0
    assert splits[0].duration_sec == 240.0
    assert splits[0].avg_power_watts == 202.0


@pytest.mark.asyncio
async def test_end_to_end_concept2_bike_ingestion(db_session: AsyncSession, sample_user):
    user, hr_profile = sample_user
    fixture_path = Path(__file__).parent.parent / "fixtures" / "concept2_samples.json"
    with open(fixture_path) as f:
        data = json.load(f)

    adapter = Concept2Adapter()
    bike_data = data["bike_workout"]
    normalized = adapter.normalize_concept2_workout(bike_data)

    workout, is_created = await ingest_workout(
        session=db_session,
        user_id=user.id,
        normalized=normalized,
        hr_profile=hr_profile,
    )
    await db_session.commit()

    assert is_created is True
    assert workout.provider == "concept2"
    assert workout.external_id == "99887766"
    assert workout.discipline == "erg_bike"
    assert workout.total_distance_m == 10000.0
    assert workout.avg_cadence_spm == 85.0
    assert workout.avg_power_watts == 225.0
