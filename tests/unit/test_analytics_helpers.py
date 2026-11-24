"""Unit tests for Phase 2 Analytics schemas, muscle group classifier, and 1RM calculation."""

import pytest
from src.schemas.analytics import CardioVolumeSummary, MuscleGroupVolumeSummary, DashboardMacroResponse
from src.schemas.workout import WorkoutTableRow, WorkoutDetailTelemetry, TelemetryPoint
from src.services.analytics_service import AnalyticsService


def test_brzycki_1rm_calculation():
    # Test 1 rep
    assert AnalyticsService.calculate_estimated_1rm(225.0, 1) == 225.0

    # Test 5 reps at 200 lbs: 200 * (36 / 32) = 225.0
    assert AnalyticsService.calculate_estimated_1rm(200.0, 5) == 225.0

    # Test 10 reps at 100 lbs: 100 * (36 / 27) = 133.3
    assert AnalyticsService.calculate_estimated_1rm(100.0, 10) == 133.3

    # Test zero or negative bounds
    assert AnalyticsService.calculate_estimated_1rm(0.0, 5) == 0.0
    assert AnalyticsService.calculate_estimated_1rm(100.0, 0) == 0.0


def test_normalize_muscle_group():
    assert AnalyticsService.normalize_muscle_group("Chest") == ("push", "Push")
    assert AnalyticsService.normalize_muscle_group("pecs") == ("push", "Push")
    assert AnalyticsService.normalize_muscle_group("deltoids") == ("push", "Push")
    assert AnalyticsService.normalize_muscle_group("triceps") == ("push", "Push")
    assert AnalyticsService.normalize_muscle_group("lats") == ("pull", "Pull")
    assert AnalyticsService.normalize_muscle_group("biceps") == ("pull", "Pull")
    assert AnalyticsService.normalize_muscle_group("arms", "Tricep Rope Pushdown") == ("push", "Push")
    assert AnalyticsService.normalize_muscle_group("arms", "Dumbbell Hammer Curl") == ("pull", "Pull")
    assert AnalyticsService.normalize_muscle_group("quadriceps") == ("legs", "Legs")
    assert AnalyticsService.normalize_muscle_group("glutes") == ("legs", "Legs")
    assert AnalyticsService.normalize_muscle_group("abs") == ("abs", "Abs")
    assert AnalyticsService.normalize_muscle_group("abs", "Hanging Leg Raise") == ("abs", "Abs")
    assert AnalyticsService.normalize_muscle_group(None) == ("other", "Other")
    assert AnalyticsService.normalize_muscle_group("full_body") == ("other", "Other")


def test_phase2_pydantic_schemas():
    cardio = CardioVolumeSummary(
        total_cardio_minutes=120.0,
        zone2_minutes=90.0,
        zone5_minutes=20.0,
        zone2_percentage=75.0,
        zone5_percentage=16.7,
    )
    assert cardio.zone2_weekly_goal_minutes == 120.0
    assert cardio.vo2max_weekly_goal_minutes == 20.0

    muscle = MuscleGroupVolumeSummary(
        muscle_group="push",
        display_name="Push",
        working_sets=12,
        weekly_avg_sets=12.0,
        weekly_goal_sets=10.0,
        goal_progress_pct=120.0,
        total_reps=96,
        top_exercise_name="Barbell Bench Press",
        top_weight_lbs=225.0,
        top_reps=5,
        estimated_1rm_lbs=253.1,
    )
    macro = DashboardMacroResponse(cardio=cardio, resistance=[muscle])
    assert macro.cardio.zone2_minutes == 90.0
    assert len(macro.resistance) == 1
    assert macro.resistance[0].top_weight_lbs == 225.0
