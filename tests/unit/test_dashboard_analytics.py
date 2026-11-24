"""Unit tests for Macro Dashboard Volume analytics calculations."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import StrengthExercise, StrengthSet, User, WorkoutSession
from src.services.analytics_service import AnalyticsService


@pytest.mark.asyncio
async def test_get_macro_dashboard_volume(db_session: AsyncSession):
    user = User(id=uuid.uuid4())
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(timezone.utc)

    # 1. Add cardio workout with Zone 2 and Zone 5
    w_cardio = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="concept2",
        external_id="test_row_interval_1",
        discipline="indoor_row",
        title="4x4 Interval Row",
        start_time_utc=now - timedelta(days=2),
        total_duration_sec=1680.0,  # 28 mins
        active_duration_sec=960.0,
        total_distance_m=4200.0,
        zone1_duration_sec=200.0,
        zone2_duration_sec=480.0,  # 8 mins
        zone3_duration_sec=100.0,
        zone4_duration_sec=500.0,
        zone5_duration_sec=400.0,  # 6.67 mins (VO2 max)
        status="active",
    )
    db_session.add(w_cardio)

    # 2. Add strength exercises & sets
    ex_bench = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Barbell Bench Press",
        slug="barbell-bench-press-test",
        category="barbell",
        primary_muscle_group="chest",
        is_bodyweight=False,
    )
    ex_squat = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Barbell Back Squat",
        slug="barbell-back-squat-test",
        category="barbell",
        primary_muscle_group="quadriceps",
        is_bodyweight=False,
    )
    db_session.add_all([ex_bench, ex_squat])
    await db_session.flush()

    w_strength = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="gym_mode",
        external_id="test_strength_1",
        discipline="strength",
        title="Heavy Upper & Lower",
        start_time_utc=now - timedelta(days=1),
        total_duration_sec=3600.0,
        active_duration_sec=3600.0,
        total_distance_m=0.0,
        status="active",
    )
    db_session.add(w_strength)
    await db_session.flush()

    # 3 sets of bench (1 warmup, 2 working: 200x5 and 225x3)
    s1 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=w_strength.id,
        exercise_id=ex_bench.id,
        set_index=1,
        reps_completed=10,
        weight=135.0,
        weight_unit="lbs",
        is_warmup=True,
        idempotency_key="test_s1",
    )
    s2 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=w_strength.id,
        exercise_id=ex_bench.id,
        set_index=2,
        reps_completed=5,
        weight=200.0,
        weight_unit="lbs",
        is_warmup=False,
        idempotency_key="test_s2",
    )
    s3 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=w_strength.id,
        exercise_id=ex_bench.id,
        set_index=3,
        reps_completed=3,
        weight=225.0,
        weight_unit="lbs",
        is_warmup=False,
        idempotency_key="test_s3",
    )
    # 2 sets of squat (working: 275x5 and 315x3)
    s4 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=w_strength.id,
        exercise_id=ex_squat.id,
        set_index=4,
        reps_completed=5,
        weight=275.0,
        weight_unit="lbs",
        is_warmup=False,
        idempotency_key="test_s4",
    )
    s5 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=w_strength.id,
        exercise_id=ex_squat.id,
        set_index=5,
        reps_completed=3,
        weight=315.0,
        weight_unit="lbs",
        is_warmup=False,
        idempotency_key="test_s5",
    )
    db_session.add_all([s1, s2, s3, s4, s5])
    await db_session.commit()

    service = AnalyticsService()
    start_dt = now - timedelta(days=7)
    end_dt = now

    macro = await service.get_macro_dashboard_volume(db_session, user.id, start_dt, end_dt)

    # Verify cardio volume: 28 min total, 8 min Zone 2, 8.3 min Zone 4, 6.7 min Zone 5 + weekly goal defaults
    assert macro.cardio.total_cardio_minutes == 28.0
    assert macro.cardio.zone2_minutes == 8.0
    assert macro.cardio.zone4_minutes == round(500.0 / 60.0, 1)
    assert macro.cardio.zone5_minutes == round(400.0 / 60.0, 1)
    assert macro.cardio.zone2_weekly_goal_minutes == 120.0
    assert macro.cardio.vo2max_weekly_goal_minutes == 20.0
    assert macro.cardio.zone2_avg_weekly_minutes == 8.0
    assert macro.cardio.zone4_avg_weekly_minutes == round(500.0 / 60.0, 1)
    assert len(macro.cardio.weekly_trend) == 1
    assert macro.cardio.weekly_trend[0].zone2_minutes == 8.0
    assert macro.cardio.weekly_trend[0].zone4_minutes == round(500.0 / 60.0, 1)

    # Verify canonical 4 categories (push, pull, legs, abs) and conditional 'other' omitted when 0
    slugs = [m.muscle_group for m in macro.resistance]
    assert slugs == ["push", "pull", "legs", "abs"]

    push_vol = next(m for m in macro.resistance if m.muscle_group == "push")
    assert push_vol.working_sets == 2  # excludes warmup
    assert push_vol.weekly_goal_sets == 10.0
    assert push_vol.weekly_avg_sets == 2.0
    assert push_vol.goal_progress_pct == 20.0
    assert push_vol.top_weight_lbs == 225.0
    assert push_vol.top_reps == 3
    assert push_vol.estimated_1rm_lbs == 238.2  # 225 * (36 / 34)

    legs_vol = next(m for m in macro.resistance if m.muscle_group == "legs")
    assert legs_vol.working_sets == 2
    assert legs_vol.top_weight_lbs == 315.0

    # Verify unmapped movement routes strictly into isolated 'other' fallback
    ex_other = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Turkish Get-Up",
        slug="turkish-get-up-test",
        category="dumbbell",
        primary_muscle_group="full_body",
        is_bodyweight=False,
    )
    db_session.add(ex_other)
    await db_session.flush()
    db_session.add(
        StrengthSet(
            id=uuid.uuid4(),
            workout_session_id=w_strength.id,
            exercise_id=ex_other.id,
            set_index=6,
            reps_completed=4,
            weight=45.0,
            weight_unit="lbs",
            is_warmup=False,
            idempotency_key="test_s6_other",
        )
    )
    await db_session.commit()

    macro_with_other = await service.get_macro_dashboard_volume(db_session, user.id, start_dt, end_dt)
    other_vol = next((m for m in macro_with_other.resistance if m.muscle_group == "other"), None)
    assert other_vol is not None
    assert other_vol.working_sets == 1
    assert other_vol.weekly_goal_sets == 0.0
