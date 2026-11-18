"""Unit tests for Personal Record (PR) detection and Epley formulas."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import WorkoutSession
from src.models.exercise import StrengthExercise
from src.models.strength_set import StrengthSet
from src.schemas.analytics import WindowPreset
from src.services.pr_detector import PRDetectorService


def test_epley_1rm_calculation():
    service = PRDetectorService()

    # 1 rep at 315 lbs = 315 lbs
    assert service.calculate_epley_1rm(315.0, 1) == 315.0

    # 5 reps at 225 lbs = 225 * (1 + 5/30) = 225 * 1.166667 = 262.5 lbs
    assert pytest.approx(service.calculate_epley_1rm(225.0, 5), 0.1) == 262.5

    # 10 reps at 200 lbs = 200 * (1 + 10/30) = 266.67 lbs
    assert pytest.approx(service.calculate_epley_1rm(200.0, 10), 0.1) == 266.7

    # > 10 reps (e.g. 11 reps) must be capped / return None (muscular endurance)
    assert service.calculate_epley_1rm(135.0, 11) is None
    assert service.calculate_epley_1rm(135.0, 15) is None


def test_estimated_5rm_calculation():
    service = PRDetectorService()
    # 5RM = 1RM / 1.1667
    e1rm = 262.5
    e5rm = service.calculate_estimated_5rm(e1rm)
    assert pytest.approx(e5rm, 0.1) == 225.0


def test_endurance_milestone_matching():
    service = PRDetectorService()

    # 5k running is 5000m (+/- 3% is 4850m to 5150m)
    assert service.match_endurance_milestone("outdoor_run", 5000.0) == "5k"
    assert service.match_endurance_milestone("outdoor_run", 4950.0) == "5k"
    assert service.match_endurance_milestone("outdoor_run", 5120.0) == "5k"
    # 4800m is outside +/- 3%
    assert service.match_endurance_milestone("outdoor_run", 4800.0) is None

    # 10k running (+/- 3% is 9700m to 10300m)
    assert service.match_endurance_milestone("outdoor_run", 10000.0) == "10k"
    assert service.match_endurance_milestone("outdoor_run", 10100.0) == "10k"

    # 1 mile running is 1609.34m (+/- 3% is 1561m to 1657m)
    assert service.match_endurance_milestone("outdoor_run", 1609.34) == "1_mile"
    assert service.match_endurance_milestone("outdoor_run", 1600.0) == "1_mile"

    # Erg 2k (+/- 3% is 1940m to 2060m)
    assert service.match_endurance_milestone("indoor_row", 2000.0) == "2k_erg"
    assert service.match_endurance_milestone("indoor_row", 1980.0) == "2k_erg"

    # Erg 500m (+/- 3% is 485m to 515m)
    assert service.match_endurance_milestone("indoor_row", 500.0) == "500m_erg"


@pytest.mark.asyncio
async def test_detect_strength_prs(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    service = PRDetectorService()
    now = datetime.now(timezone.utc)

    # Session
    sess = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="manual_gym",
        external_id=f"gym-{uuid.uuid4()}",
        discipline="strength",
        title="Bench Day",
        start_time_utc=now - timedelta(days=2),
        total_duration_sec=2400.0,
        active_duration_sec=2000.0,
    )
    db_session.add(sess)

    bench = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Barbell Bench Press",
        slug="barbell-bench-press",
        category="barbell",
        primary_muscle_group="chest",
        is_bodyweight=False,
    )
    db_session.add(bench)
    await db_session.flush()

    # Set 1: 225 x 5 (estimated 1RM ~262.5 lbs)
    set1 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=sess.id,
        exercise_id=bench.id,
        set_index=1,
        reps_completed=5,
        weight=225.0,
        weight_unit="lbs",
        is_warmup=False,
        idempotency_key="b1",
    )
    # Set 2: 245 x 3 (estimated 1RM = 245 * (1 + 3/30) = 245 * 1.1 = 269.5 lbs -> NEW PR!)
    set2 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=sess.id,
        exercise_id=bench.id,
        set_index=2,
        reps_completed=3,
        weight=245.0,
        weight_unit="lbs",
        is_warmup=False,
        idempotency_key="b2",
    )
    db_session.add_all([set1, set2])
    await db_session.commit()

    prs = await service.get_all_prs(db_session, user.id, window=WindowPreset.ALL_TIME)
    bench_prs = [p for p in prs if p.exercise_name == "Barbell Bench Press"]

    assert len(bench_prs) >= 1
    best_1rm_pr = next((p for p in bench_prs if p.milestone_type == "estimated_1rm_pr"), None)
    assert best_1rm_pr is not None
    assert pytest.approx(best_1rm_pr.record_value, 0.1) == 269.5
    assert best_1rm_pr.record_unit == "lbs"
