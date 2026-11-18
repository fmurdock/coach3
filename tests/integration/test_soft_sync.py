"""Integration test for soft-sync and upstream edit reconciliation."""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.base import NormalizedWorkout
from src.services.ingestion import ingest_workout


@pytest.mark.asyncio
async def test_upstream_edit_preserves_local_user_notes(db_session: AsyncSession, sample_user):
    user, hr_profile = sample_user
    now = datetime.now(timezone.utc)

    # Initial sync
    initial_workout = NormalizedWorkout(
        provider="polar",
        external_id="polar_run_edit_test",
        discipline="outdoor_run",
        title="Initial Polar Run",
        start_time_utc=now,
        local_timezone="UTC",
        total_duration_sec=1800.0,
        active_duration_sec=1800.0,
        total_distance_m=5000.0,
    )

    workout, is_created = await ingest_workout(db_session, user.id, initial_workout, hr_profile)
    workout.user_notes = "Felt great, practiced cadence drills!"
    await db_session.commit()
    assert is_created is True

    # Athlete edited title and trimmed 100m on Polar Flow
    edited_workout = NormalizedWorkout(
        provider="polar",
        external_id="polar_run_edit_test",
        discipline="outdoor_run",
        title="Morning 5K Tempo (Renamed)",
        start_time_utc=now,
        local_timezone="UTC",
        total_duration_sec=1780.0,
        active_duration_sec=1780.0,
        total_distance_m=4950.0,
    )

    updated_workout, is_new = await ingest_workout(db_session, user.id, edited_workout, hr_profile)
    await db_session.commit()

    assert is_new is False
    assert updated_workout.id == workout.id
    assert updated_workout.title == "Morning 5K Tempo (Renamed)"
    assert updated_workout.total_distance_m == 4950.0
    assert updated_workout.total_duration_sec == 1780.0
    # Crucial: User note must be preserved!
    assert updated_workout.user_notes == "Felt great, practiced cadence drills!"
