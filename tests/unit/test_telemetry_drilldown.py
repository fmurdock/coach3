"""Unit tests for workout detail telemetry, interval slicing, and superimposed curves."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import HeartRateSample, User, WorkoutSession, WorkoutSplit
from src.services.analytics_service import AnalyticsService


@pytest.mark.asyncio
async def test_build_interval_consistency_analysis(db_session: AsyncSession):
    user = User(id=uuid.uuid4())
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    w = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="concept2",
        external_id="interval_test_4x4",
        discipline="indoor_row",
        title="4x4min Concept2 Intervals",
        start_time_utc=now,
        total_duration_sec=1680.0,
        active_duration_sec=960.0,
        total_distance_m=4220.0,
        avg_heart_rate=156,
        max_heart_rate=184,
        status="active",
    )
    db_session.add(w)
    await db_session.flush()

    # Add 4 work splits and 3 rest splits
    sp1 = WorkoutSplit(
        id=uuid.uuid4(),
        workout_id=w.id,
        split_index=1,
        split_type="interval",
        duration_sec=240.0,
        distance_m=1055.0,
        avg_split_sec_per_500m=113.7,
        avg_heart_rate=162,
    )
    sp2 = WorkoutSplit(
        id=uuid.uuid4(),
        workout_id=w.id,
        split_index=2,
        split_type="rest",
        duration_sec=240.0,
        distance_m=0.0,
        avg_split_sec_per_500m=None,
        avg_heart_rate=132,
    )
    sp3 = WorkoutSplit(
        id=uuid.uuid4(),
        workout_id=w.id,
        split_index=3,
        split_type="interval",
        duration_sec=240.0,
        distance_m=1060.0,
        avg_split_sec_per_500m=113.2,
        avg_heart_rate=166,
    )
    sp4 = WorkoutSplit(
        id=uuid.uuid4(),
        workout_id=w.id,
        split_index=4,
        split_type="rest",
        duration_sec=240.0,
        distance_m=0.0,
        avg_split_sec_per_500m=None,
        avg_heart_rate=136,
    )
    sp5 = WorkoutSplit(
        id=uuid.uuid4(),
        workout_id=w.id,
        split_index=5,
        split_type="interval",
        duration_sec=240.0,
        distance_m=1053.0,
        avg_split_sec_per_500m=113.9,
        avg_heart_rate=169,
    )
    sp6 = WorkoutSplit(
        id=uuid.uuid4(),
        workout_id=w.id,
        split_index=6,
        split_type="rest",
        duration_sec=240.0,
        distance_m=0.0,
        avg_split_sec_per_500m=None,
        avg_heart_rate=138,
    )
    sp7 = WorkoutSplit(
        id=uuid.uuid4(),
        workout_id=w.id,
        split_index=7,
        split_type="interval",
        duration_sec=240.0,
        distance_m=1052.0,
        avg_split_sec_per_500m=114.1,
        avg_heart_rate=172,
    )
    db_session.add_all([sp1, sp2, sp3, sp4, sp5, sp6, sp7])

    # Add sample HR points for split 1 (0 to 240s) and split 3 (480 to 720s)
    for s in range(0, 241, 60):
        db_session.add(HeartRateSample(
            workout_id=w.id,
            timestamp_utc=now + timedelta(seconds=s),
            elapsed_sec=float(s),
            bpm=145 + int(s / 10),
        ))
    for s in range(480, 721, 60):
        db_session.add(HeartRateSample(
            workout_id=w.id,
            timestamp_utc=now + timedelta(seconds=s),
            elapsed_sec=float(s),
            bpm=150 + int((s - 480) / 10),
        ))
    await db_session.commit()

    service = AnalyticsService()
    detail = await service.get_workout_detail_telemetry(db_session, w.id)

    assert detail is not None
    assert detail.workout_id == w.id
    assert len(detail.splits) == 7
    assert detail.interval_consistency is not None
    assert len(detail.interval_consistency.superimposed_curves) == 4  # 4 work sets
    assert detail.interval_consistency.is_consistent is True

    # First curve points should have set_elapsed_sec in [0, 240], heart_rate & pace_sec
    set1_pts = detail.interval_consistency.superimposed_curves[0].points
    assert len(set1_pts) > 0
    assert set1_pts[0].set_elapsed_sec == 0.0
    assert set1_pts[-1].set_elapsed_sec == 240.0
    assert any(pt.heart_rate is not None for pt in set1_pts)
    assert any(pt.pace_sec is not None for pt in set1_pts)


@pytest.mark.asyncio
async def test_strength_detail_notes_and_sets_no_synthetic_series(db_session: AsyncSession):
    from src.models import StrengthExercise, StrengthSet

    user = User(id=uuid.uuid4())
    db_session.add(user)
    await db_session.flush()

    ex = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Barbell Deadlift",
        slug="barbell-deadlift-drilldown",
        category="barbell",
        primary_muscle_group="hamstrings",
        is_bodyweight=False,
    )
    db_session.add(ex)
    await db_session.flush()

    w = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="gym_mode",
        external_id="strength_drill_1",
        discipline="strength",
        title="Deadlift Day",
        start_time_utc=datetime.now(timezone.utc),
        total_duration_sec=2400.0,
        active_duration_sec=2400.0,
        user_notes="Felt snappy off the floor.",
        status="active",
    )
    db_session.add(w)
    await db_session.flush()

    db_session.add(
        StrengthSet(
            id=uuid.uuid4(),
            workout_session_id=w.id,
            exercise_id=ex.id,
            set_index=1,
            reps_completed=5,
            weight=315.0,
            weight_unit="lbs",
            rpe=8.0,
            is_warmup=False,
            idempotency_key="dl_drill_1",
        )
    )
    await db_session.commit()

    service = AnalyticsService()
    detail = await service.get_workout_detail_telemetry(db_session, w.id)

    assert detail is not None
    assert detail.user_notes == "Felt snappy off the floor."
    assert detail.time_series == []
    assert len(detail.strength_sets) == 1
    assert detail.strength_sets[0].exercise_name == "Barbell Deadlift"
    assert detail.strength_sets[0].category == "legs"
    assert detail.strength_sets[0].weight_lbs == 315.0
    assert detail.strength_sets[0].rpe == 8.0
