"""Unit tests for AnalyticsService (Cardio & Zone 2 metrics)."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import WorkoutSession
from src.schemas.analytics import WindowPreset
from src.services.analytics_service import AnalyticsService


@pytest.mark.asyncio
async def test_resolve_date_window():
    service = AnalyticsService()
    now = datetime.now(timezone.utc)
    
    # 7d window
    start_7d, end_7d = service.resolve_date_window(WindowPreset.SEVEN_DAYS)
    assert (end_7d - start_7d).days == 7

    # 30d window
    start_30d, end_30d = service.resolve_date_window(WindowPreset.THIRTY_DAYS)
    assert (end_30d - start_30d).days == 30

    # Custom window
    custom_start = (now - timedelta(days=15)).date()
    custom_end = now.date()
    start_c, end_c = service.resolve_date_window(None, start_date=custom_start, end_date=custom_end)
    assert start_c.date() == custom_start
    assert end_c.date() == custom_end


@pytest.mark.asyncio
async def test_cardio_metrics_empty(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    service = AnalyticsService()
    
    start, end = service.resolve_date_window(WindowPreset.THIRTY_DAYS)
    res = await service.get_cardio_metrics(db_session, user.id, start, end)
    
    assert res.total_distance_km == 0.0
    assert res.total_distance_miles == 0.0
    assert res.total_duration_hours == 0.0
    assert res.zone2_duration_hours == 0.0
    assert res.zone2_percentage == 0.0
    assert res.outdoor_run_km == 0.0
    assert res.erg_row_meters == 0.0
    assert res.erg_bike_meters == 0.0
    assert isinstance(res.weekly_trend, list)


@pytest.mark.asyncio
async def test_cardio_metrics_aggregations(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    service = AnalyticsService()
    now = datetime.now(timezone.utc)

    # 1. Outdoor run: 10 km (10000m), 3600 sec total, 2700 sec Zone 2
    run = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="polar",
        external_id="polar-run-101",
        discipline="outdoor_run",
        title="Morning 10k",
        start_time_utc=now - timedelta(days=2),
        total_duration_sec=3600.0,
        active_duration_sec=3600.0,
        total_distance_m=10000.0,
        zone1_duration_sec=300.0,
        zone2_duration_sec=2700.0,
        zone3_duration_sec=600.0,
        zone4_duration_sec=0.0,
        zone5_duration_sec=0.0,
        avg_pace_sec_per_km=360.0,
    )

    # 2. Indoor row: 5,000 m, 1200 sec total, 900 sec Zone 2
    row = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="concept2",
        external_id="c2-row-201",
        discipline="indoor_row",
        title="5k Row Erg",
        start_time_utc=now - timedelta(days=5),
        total_duration_sec=1200.0,
        active_duration_sec=1200.0,
        total_distance_m=5000.0,
        zone1_duration_sec=100.0,
        zone2_duration_sec=900.0,
        zone3_duration_sec=200.0,
        zone4_duration_sec=0.0,
        zone5_duration_sec=0.0,
        avg_split_sec_per_500m=120.0,
    )

    # 3. Erg bike: 15,000 m, 1800 sec total, 1500 sec Zone 2
    bike = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="concept2",
        external_id="c2-bike-301",
        discipline="erg_bike",
        title="Bike Erg 15k",
        start_time_utc=now - timedelta(days=10),
        total_duration_sec=1800.0,
        active_duration_sec=1800.0,
        total_distance_m=15000.0,
        zone1_duration_sec=100.0,
        zone2_duration_sec=1500.0,
        zone3_duration_sec=200.0,
        zone4_duration_sec=0.0,
        zone5_duration_sec=0.0,
    )

    db_session.add_all([run, row, bike])
    await db_session.commit()

    start, end = service.resolve_date_window(WindowPreset.THIRTY_DAYS)
    metrics = await service.get_cardio_metrics(db_session, user.id, start, end)

    # Distances
    # Total distance: 10000m + 5000m + 15000m = 30000m = 30.0 km
    assert pytest.approx(metrics.total_distance_km, 0.01) == 30.0
    assert pytest.approx(metrics.total_distance_miles, 0.01) == 18.64
    assert pytest.approx(metrics.outdoor_run_km, 0.01) == 10.0
    assert metrics.erg_row_meters == 5000.0
    assert metrics.erg_bike_meters == 15000.0

    # Total duration: 3600 + 1200 + 1800 = 6600 sec = 1.8333 hours
    assert pytest.approx(metrics.total_duration_hours, 0.01) == 1.83

    # Zone 2 duration: 2700 + 900 + 1500 = 5100 sec = 1.4167 hours
    assert pytest.approx(metrics.zone2_duration_hours, 0.01) == 1.42

    # Zone 2 percentage: 5100 / 6600 * 100 = 77.27%
    assert pytest.approx(metrics.zone2_percentage, 0.1) == 77.3

    # Weekly trend
    assert len(metrics.weekly_trend) > 0


@pytest.mark.asyncio
async def test_strength_metrics_effective_sets_and_volume(db_session: AsyncSession, sample_user):
    from src.models.exercise import StrengthExercise
    from src.models.strength_set import StrengthSet

    user, _ = sample_user
    service = AnalyticsService()
    now = datetime.now(timezone.utc)

    # 1. Create Strength Session
    session_obj = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="manual_gym",
        external_id=f"gym-{uuid.uuid4()}",
        discipline="strength",
        title="Leg & Back Day",
        start_time_utc=now - timedelta(days=3),
        total_duration_sec=3600.0,
        active_duration_sec=3000.0,
    )
    db_session.add(session_obj)

    # 2. Exercises: Squat (quadriceps), Pull-up (back, bodyweight)
    squat = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Barbell Back Squat",
        slug="barbell-back-squat",
        category="barbell",
        primary_muscle_group="quadriceps",
        is_bodyweight=False,
    )
    pullup = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Pull-Up",
        slug="pull-up",
        category="bodyweight",
        primary_muscle_group="back",
        is_bodyweight=True,
    )
    db_session.add_all([squat, pullup])
    await db_session.flush()

    # 3. Sets:
    # - Warmup Squat: 135 lbs x 10 reps (is_warmup=True) -> Should be excluded from effective sets
    set1 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=session_obj.id,
        exercise_id=squat.id,
        set_index=1,
        reps_completed=10,
        weight=135.0,
        weight_unit="lbs",
        is_warmup=True,
        idempotency_key="k1",
    )
    # - Working Squat: 225 lbs x 5 reps (is_warmup=False) -> 1125 lbs
    set2 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=session_obj.id,
        exercise_id=squat.id,
        set_index=2,
        reps_completed=5,
        weight=225.0,
        weight_unit="lbs",
        is_warmup=False,
        idempotency_key="k2",
    )
    # - Working Squat 2: 225 lbs x 5 reps -> 1125 lbs
    set3 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=session_obj.id,
        exercise_id=squat.id,
        set_index=3,
        reps_completed=5,
        weight=225.0,
        weight_unit="lbs",
        is_warmup=False,
        idempotency_key="k3",
    )
    # - Weighted Pull-Up: 10 reps with +30 lbs -> 300 lbs added calisthenic load
    set4 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=session_obj.id,
        exercise_id=pullup.id,
        set_index=4,
        reps_completed=10,
        weight=0.0,
        weight_unit="lbs",
        is_bodyweight=True,
        added_weight=30.0,
        is_warmup=False,
        idempotency_key="k4",
    )
    # - Bodyweight Pull-Up in kg: 10 reps with +10 kg (10 * 2.20462 = 22.05 lbs) -> ~220.5 lbs
    set5 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=session_obj.id,
        exercise_id=pullup.id,
        set_index=5,
        reps_completed=10,
        weight=0.0,
        weight_unit="kg",
        is_bodyweight=True,
        added_weight=10.0,
        is_warmup=False,
        idempotency_key="k5",
    )

    db_session.add_all([set1, set2, set3, set4, set5])
    await db_session.commit()

    start, end = service.resolve_date_window(WindowPreset.THIRTY_DAYS)
    strength = await service.get_strength_metrics(db_session, user.id, start, end)

    # Effective working sets: 4 (warmup excluded!)
    assert strength.effective_working_sets == 4
    # Total reps: 5 + 5 + 10 + 10 = 30 reps for working sets (or 40 total reps)
    assert strength.total_reps in (30, 40)

    # Muscle group sets: quadriceps: 2, back: 2
    assert strength.muscle_group_sets.get("quadriceps") == 2
    assert strength.muscle_group_sets.get("back") == 2

    # Calisthenic added load: 30*10 + (10*2.20462)*10 = 300 + 220.46 = 520.46 lbs
    assert pytest.approx(strength.added_calisthenic_load_lbs, 0.1) == 520.5

    # Volume load: 1125 + 1125 + 520.46 = 2770.46 lbs
    assert pytest.approx(strength.total_volume_load_lbs, 1.0) == 2770.5


@pytest.mark.asyncio
async def test_polar_pace_dynamic_variation_from_hr(db_session: AsyncSession, sample_user):
    from src.models.telemetry import HeartRateSample
    user, _ = sample_user
    service = AnalyticsService()
    now = datetime.now(timezone.utc)

    # Polar run with varying heart rate samples and no splits/GPS
    run = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="polar",
        external_id="polar-run-varying-hr",
        discipline="outdoor_run",
        title="Polar Run - Polar BEAT",
        start_time_utc=now,
        total_duration_sec=600.0,
        active_duration_sec=600.0,
        total_distance_m=1500.0,
        avg_pace_sec_per_km=400.0,
        avg_heart_rate=135,
    )
    db_session.add(run)

    # Add 20 HR samples with clear cardiac elevation (surges)
    for i in range(20):
        sample_hr = 120 if i < 10 else 155
        s = HeartRateSample(
            workout_id=run.id,
            timestamp_utc=now + timedelta(seconds=i * 10),
            elapsed_sec=float(i * 10),
            bpm=sample_hr,
        )
        db_session.add(s)

    await db_session.commit()

    detail = await service.get_workout_detail_telemetry(db_session, run.id)
    assert detail is not None
    assert len(detail.time_series) == 20

    paces = [pt.pace_sec for pt in detail.time_series]
    # Pace should NOT be a flat line
    assert min(paces) < max(paces)
    # Higher HR points should have faster pace (lower sec/km) than lower HR points
    assert paces[-1] < paces[0]


@pytest.mark.asyncio
async def test_concept2_stroke_telemetry_in_detail(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    service = AnalyticsService()
    now = datetime.now(timezone.utc)

    c2_workout = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="concept2",
        external_id="c2-stroke-telemetry",
        discipline="indoor_row",
        title="Concept2 Indoor Rower Session",
        start_time_utc=now,
        total_duration_sec=240.0,
        active_duration_sec=240.0,
        total_distance_m=1038.0,
        avg_split_sec_per_500m=115.6,
        raw_summary={
            "strokes": [
                {"t": 11, "p": 1584, "hr": 90, "spm": 0, "d": 35},
                {"t": 31, "p": 1265, "hr": 94, "spm": 31, "d": 116},
                {"t": 201, "p": 1044, "hr": 126, "spm": 31, "d": 913},
            ]
        },
    )
    db_session.add(c2_workout)
    await db_session.commit()

    detail = await service.get_workout_detail_telemetry(db_session, c2_workout.id)
    assert detail is not None
    assert len(detail.time_series) == 3
    assert detail.time_series[0].elapsed_sec == 1.1
    assert detail.time_series[0].heart_rate == 90
    assert detail.time_series[0].pace_sec == 158.4
    assert detail.time_series[2].elapsed_sec == 20.1
    assert detail.time_series[2].heart_rate == 126
    assert detail.time_series[2].pace_sec == 104.4


@pytest.mark.asyncio
async def test_concept2_multi_interval_telemetry_and_per_interval_graphs(db_session: AsyncSession, sample_user):
    from src.models.telemetry import WorkoutSplit
    user, _ = sample_user
    service = AnalyticsService()
    now = datetime.now(timezone.utc)

    c2_workout = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="concept2",
        external_id="c2-multi-interval",
        discipline="indoor_row",
        title="Concept2 Indoor Rower Session",
        start_time_utc=now,
        total_duration_sec=480.0,
        active_duration_sec=480.0,
        total_distance_m=2071.0,
        avg_split_sec_per_500m=115.8,
        raw_summary={
            "rest_distance": 56,
            "workout": {
                "intervals": [
                    {
                        "time": 2400,
                        "distance": 1038,
                        "rest_time": 2400,
                        "heart_rate": {"average": 154, "ending": 167, "max": 167, "rest": 112},
                    },
                    {
                        "time": 2400,
                        "distance": 1033,
                        "rest_time": 2400,
                        "heart_rate": {"average": 163, "ending": 173, "max": 174, "rest": 106},
                    },
                ]
            },
            "strokes": [
                {"t": 11, "p": 1584, "hr": 90, "spm": 0, "d": 35},
                {"t": 2385, "p": 1167, "hr": 167, "spm": 31, "d": 10314},
                {"t": 7, "p": 0, "hr": 110, "spm": 0, "d": 25},
                {"t": 2399, "p": 1236, "hr": 173, "spm": 30, "d": 10324},
            ],
        },
    )
    db_session.add(c2_workout)
    db_session.add_all([
        WorkoutSplit(
            id=uuid.uuid4(),
            workout_id=c2_workout.id,
            split_index=1,
            split_type="interval",
            distance_m=1038.0,
            duration_sec=240.0,
            avg_split_sec_per_500m=115.6,
            avg_power_watts=226.6,
            avg_cadence_spm=31.0,
            avg_heart_rate=154,
        ),
        WorkoutSplit(
            id=uuid.uuid4(),
            workout_id=c2_workout.id,
            split_index=2,
            split_type="rest",
            distance_m=0.0,
            duration_sec=240.0,
            avg_heart_rate=112,
        ),
        WorkoutSplit(
            id=uuid.uuid4(),
            workout_id=c2_workout.id,
            split_index=3,
            split_type="interval",
            distance_m=1033.0,
            duration_sec=240.0,
            avg_split_sec_per_500m=116.1,
            avg_power_watts=223.1,
            avg_cadence_spm=32.0,
            avg_heart_rate=163,
        ),
    ])
    await db_session.commit()

    detail = await service.get_workout_detail_telemetry(db_session, c2_workout.id)
    assert detail is not None
    assert detail.rest_distance_m == 56.0

    # Time series spans Interval 1 (0..240), Rest 1 break + HR recovery (240..480), Interval 2 (480..720)
    assert len(detail.time_series) == 6
    assert detail.time_series[0].elapsed_sec == 1.1
    assert detail.time_series[1].elapsed_sec == 238.5
    # Rest period markers
    assert detail.time_series[2].pace_sec is None
    assert detail.time_series[3].heart_rate == 112
    # Interval 2 strokes properly offset to 480s+ and p==0 converted to None
    assert detail.time_series[4].elapsed_sec == 480.7
    assert detail.time_series[4].pace_sec is None
    assert detail.time_series[5].elapsed_sec == 719.9
    assert detail.time_series[5].cadence_spm == 30.0

    # Per-split details include ending_heart_rate, peak_heart_rate, and individual samples for Interval 1 and 2
    assert len(detail.splits) == 3
    assert detail.splits[0].ending_heart_rate == 167
    assert detail.splits[0].peak_heart_rate == 167
    assert len(detail.splits[0].samples) == 2
    assert detail.splits[0].samples[0].set_elapsed_sec == 1.1
    assert detail.splits[0].samples[1].set_elapsed_sec == 238.5

    assert detail.splits[2].ending_heart_rate == 173
    assert detail.splits[2].peak_heart_rate == 174
    assert len(detail.splits[2].samples) == 2
    assert detail.splits[2].samples[0].set_elapsed_sec == 0.7
    assert detail.splits[2].samples[0].heart_rate == 110
    assert detail.splits[2].samples[1].set_elapsed_sec == 239.9
    assert detail.splits[2].samples[1].heart_rate == 173

    # Superimposed curves get separate curves for both Interval 1 and Interval 2
    assert detail.interval_consistency is not None
    curves = detail.interval_consistency.superimposed_curves
    assert len(curves) == 2
    assert len(curves[0].points) == 2
    assert len(curves[1].points) == 2
    assert curves[1].points[1].heart_rate == 173

