"""Integration tests for Polar running workout ingestion."""

import json
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.polar import PolarAdapter
from src.models import GPSRoutePoint, HeartRateSample, User, WorkoutSession
from src.services.ingestion import ingest_workout


@pytest.mark.asyncio
async def test_end_to_end_polar_run_ingestion(db_session: AsyncSession, sample_user):
    user, hr_profile = sample_user
    fixture_path = Path(__file__).parent.parent / "fixtures" / "polar_samples.json"
    with open(fixture_path) as f:
        data = json.load(f)

    adapter = PolarAdapter()
    exercise = data["exercises"][0]
    samples = data["samples"]

    # 1. Normalize Polar payload
    normalized = adapter.normalize_polar_exercise(exercise, samples)

    # 2. Ingest into database
    workout, is_created = await ingest_workout(
        session=db_session,
        user_id=user.id,
        normalized=normalized,
        hr_profile=hr_profile,
    )
    await db_session.commit()

    assert is_created is True
    assert workout.provider == "polar"
    assert workout.external_id == "987654321"
    assert workout.discipline == "outdoor_run"
    assert workout.total_distance_m == 10000.0
    assert workout.total_duration_sec == 3600.0
    assert workout.avg_heart_rate == 130
    assert workout.elevation_gain_m == 45.0
    assert workout.avg_pace_sec_per_km == 360.0

    # Zone 2 verification (samples are in Zone 2 between bpm 114 and 133)
    assert workout.zone2_duration_sec > 0.0

    # 3. Verify database rows directly
    # Check WorkoutSession
    q_ws = select(WorkoutSession).where(WorkoutSession.external_id == "987654321")
    res_ws = await db_session.execute(q_ws)
    stored_workout = res_ws.scalar_one()
    assert stored_workout.id == workout.id

    # Check HeartRateSamples
    q_hr = select(HeartRateSample).where(HeartRateSample.workout_id == workout.id)
    res_hr = await db_session.execute(q_hr)
    hr_rows = res_hr.scalars().all()
    assert len(hr_rows) == 7

    # Check GPSRoutePoints
    q_gps = select(GPSRoutePoint).where(GPSRoutePoint.workout_id == workout.id)
    res_gps = await db_session.execute(q_gps)
    gps_rows = res_gps.scalars().all()
    assert len(gps_rows) == 7
    assert gps_rows[0].latitude == 37.7749
    assert gps_rows[0].longitude == -122.4194
