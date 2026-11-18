"""Unit tests and golden test suite for Gym Mode natural language parser."""

import pytest
from src.services.gym_parser import GymParser


@pytest.fixture
def parser():
    return GymParser()


def test_standard_compound_sets_by_reps_at_weight(parser):
    result = parser.parse("5 sets by 8 reps of back squat at 185 pounds")
    assert result.confidence_score >= 0.90
    assert len(result.parsed_sets) == 1

    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Back Squat"
    assert item.sets == 5
    assert item.reps == 8
    assert item.weight == 185.0
    assert item.weight_unit == "lbs"
    assert item.is_bodyweight is False
    assert item.added_weight == 0.0


def test_compact_shorthand_3x5_bench(parser):
    result = parser.parse("3x5 bench at 225 lbs")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Bench Press"
    assert item.sets == 3
    assert item.reps == 5
    assert item.weight == 225.0


def test_shorthand_3_sets_of_5_on_bench(parser):
    result = parser.parse("3 sets of 5 at 225 on bench")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Bench Press"
    assert item.sets == 3
    assert item.reps == 5
    assert item.weight == 225.0


def test_single_heavy_set_deadlift(parser):
    result = parser.parse("did a heavy single at 315 on deadlift")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Deadlift"
    assert item.sets == 1
    assert item.reps == 1
    assert item.weight == 315.0


def test_triple_at_weight(parser):
    result = parser.parse("3 reps at 405 deadlift")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Deadlift"
    assert item.sets == 1
    assert item.reps == 3
    assert item.weight == 405.0


def test_dumbbell_with_plural_weights(parser):
    result = parser.parse("4 sets of 10 dumbbell bench with 70s")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Dumbbell Bench Press"
    assert item.sets == 4
    assert item.reps == 10
    assert item.weight == 70.0


def test_plate_math_two_plates(parser):
    result = parser.parse("3 reps on deadlift at two plates")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Deadlift"
    assert item.weight == 225.0


def test_plate_math_one_plate(parser):
    result = parser.parse("5 reps bench press at one plate")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Bench Press"
    assert item.weight == 135.0


def test_plate_math_the_bar(parser):
    result = parser.parse("10 reps overhead press with the bar")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Overhead Press"
    assert item.weight == 45.0


def test_metric_kilograms_support(parser):
    result = parser.parse("3 sets of 5 squats at 100 kilos")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.weight == 100.0
    assert item.weight_unit == "kg"


def test_weighted_pullups_with_extra_load(parser):
    result = parser.parse("3 sets of 12 pullups with an extra 30 pounds added")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Pull-Up"
    assert item.sets == 3
    assert item.reps == 12
    assert item.is_bodyweight is True
    assert item.weight == 0.0
    assert item.added_weight == 30.0


def test_pure_bodyweight_pushups(parser):
    result = parser.parse("4 sets of 15 pushups bodyweight only")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Push-Up"
    assert item.sets == 4
    assert item.reps == 15
    assert item.is_bodyweight is True
    assert item.weight == 0.0
    assert item.added_weight == 0.0


def test_assisted_dips_counterweight(parser):
    result = parser.parse("3 sets of 8 assisted dips minus 20 pounds")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Dip"
    assert item.sets == 3
    assert item.reps == 8
    assert item.is_bodyweight is True
    assert item.weight == 0.0
    assert item.added_weight == -20.0


def test_chin_ups_plus_twenty_five_pounds(parser):
    result = parser.parse("3 sets of 8 chinups plus 25 lbs")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Chin-Up"
    assert item.sets == 3
    assert item.reps == 8
    assert item.is_bodyweight is True
    assert item.weight == 0.0
    assert item.added_weight == 25.0


def test_rpe_explicit_decimal(parser):
    result = parser.parse("did a heavy single at 315 on deadlift, felt like RPE 8.5")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Deadlift"
    assert item.sets == 1
    assert item.reps == 1
    assert item.weight == 315.0
    assert item.rpe == 8.5


def test_reps_in_reserve_conversion(parser):
    result = parser.parse("5 reps at 225 on bench with 2 reps in reserve")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Bench Press"
    assert item.sets == 1
    assert item.reps == 5
    assert item.weight == 225.0
    assert item.rpe == 8.0


def test_rest_interval_minutes_and_rpe(parser):
    result = parser.parse("3 sets of 8 back squats at 185 at RPE 8, rest 2 minutes")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Barbell Back Squat"
    assert item.sets == 3
    assert item.reps == 8
    assert item.weight == 185.0
    assert item.rpe == 8.0
    assert item.rest_seconds == 120


def test_rest_interval_seconds(parser):
    result = parser.parse("3 sets of 10 pullups rest 90 seconds")
    assert len(result.parsed_sets) == 1
    item = result.parsed_sets[0]
    assert item.exercise_name == "Pull-Up"
    assert item.rest_seconds == 90


def test_multi_exercise_followed_by(parser):
    result = parser.parse("3 sets of 10 dumbbell lunges with 50s, followed by 3 sets of 15 calf raises")
    assert len(result.parsed_sets) == 2

    lunge = result.parsed_sets[0]
    assert lunge.exercise_name == "Dumbbell Lunge"
    assert lunge.sets == 3
    assert lunge.reps == 10
    assert lunge.weight == 50.0

    calf = result.parsed_sets[1]
    assert calf.exercise_name == "Calf Raise"
    assert calf.sets == 3
    assert calf.reps == 15


def test_multi_exercise_then_compound(parser):
    result = parser.parse("5 sets of 5 back squat at 225 then 3 sets of 8 bench at 185")
    assert len(result.parsed_sets) == 2

    squat = result.parsed_sets[0]
    assert squat.exercise_name == "Barbell Back Squat"
    assert squat.sets == 5
    assert squat.reps == 5
    assert squat.weight == 225.0

    bench = result.parsed_sets[1]
    assert bench.exercise_name == "Barbell Bench Press"
    assert bench.sets == 3
    assert bench.reps == 8
    assert bench.weight == 185.0





# --- Golden Test Suite: Extended Gym Phrasings & Movements ---

def test_golden_power_cleans(parser):
    result = parser.parse("3 sets of 2 power cleans at 185")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Power Clean"
    assert result.parsed_sets[0].sets == 3
    assert result.parsed_sets[0].reps == 2
    assert result.parsed_sets[0].weight == 185.0


def test_golden_snatch(parser):
    result = parser.parse("snatch 1 set of 3 at 135")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Snatch"
    assert result.parsed_sets[0].sets == 1
    assert result.parsed_sets[0].reps == 3
    assert result.parsed_sets[0].weight == 135.0


def test_golden_barbell_shrugs(parser):
    result = parser.parse("4 sets of 12 barbell shrugs with 225")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Barbell Shrug"
    assert result.parsed_sets[0].sets == 4
    assert result.parsed_sets[0].reps == 12
    assert result.parsed_sets[0].weight == 225.0


def test_golden_bicep_curls(parser):
    result = parser.parse("3 sets of 10 bicep curls at 65 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Barbell Bicep Curl"
    assert result.parsed_sets[0].weight == 65.0


def test_golden_skull_crushers(parser):
    result = parser.parse("3 sets of 12 skull crushers with 75 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Skull Crusher"
    assert result.parsed_sets[0].sets == 3
    assert result.parsed_sets[0].reps == 12
    assert result.parsed_sets[0].weight == 75.0


def test_golden_incline_bench(parser):
    result = parser.parse("4 sets of 6 incline bench at 205")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Incline Barbell Bench Press"
    assert result.parsed_sets[0].sets == 4
    assert result.parsed_sets[0].reps == 6
    assert result.parsed_sets[0].weight == 205.0


def test_golden_decline_bench(parser):
    result = parser.parse("3 sets of 8 decline bench at 195")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Decline Barbell Bench Press"
    assert result.parsed_sets[0].weight == 195.0


def test_golden_hip_thrusts(parser):
    result = parser.parse("4 sets of 10 hip thrusts at 315 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Barbell Hip Thrust"
    assert result.parsed_sets[0].weight == 315.0


def test_golden_zercher_squat(parser):
    result = parser.parse("3 sets of 5 zercher squats at 185")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Zercher Squat"
    assert result.parsed_sets[0].weight == 185.0


def test_golden_db_lateral_raises(parser):
    result = parser.parse("4 sets of 15 lateral raises with 25s")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Dumbbell Lateral Raise"
    assert result.parsed_sets[0].sets == 4
    assert result.parsed_sets[0].reps == 15
    assert result.parsed_sets[0].weight == 25.0


def test_golden_db_rows(parser):
    result = parser.parse("3 sets of 10 db rows with 85s")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Dumbbell Row"
    assert result.parsed_sets[0].weight == 85.0


def test_golden_goblet_squat(parser):
    result = parser.parse("3 sets of 12 goblet squats with 60 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Goblet Squat"
    assert result.parsed_sets[0].weight == 60.0


def test_golden_muscle_ups(parser):
    result = parser.parse("3 sets of 5 muscle ups bodyweight only")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Muscle-Up"
    assert result.parsed_sets[0].is_bodyweight is True
    assert result.parsed_sets[0].weight == 0.0


def test_golden_inverted_rows(parser):
    result = parser.parse("4 sets of 12 inverted rows bodyweight")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Inverted Row"
    assert result.parsed_sets[0].is_bodyweight is True


def test_golden_hanging_leg_raises(parser):
    result = parser.parse("3 sets of 15 hanging leg raises")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Hanging Leg Raise"
    assert result.parsed_sets[0].is_bodyweight is True


def test_golden_ab_wheel_rollouts(parser):
    result = parser.parse("3 sets of 12 ab wheel rollouts")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Ab Wheel Rollout"
    assert result.parsed_sets[0].is_bodyweight is True


def test_golden_lat_pulldown(parser):
    result = parser.parse("4 sets of 10 lat pulldown at 160 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Lat Pulldown"
    assert result.parsed_sets[0].weight == 160.0


def test_golden_seated_cable_row(parser):
    result = parser.parse("3 sets of 12 seated cable row at 140 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Seated Cable Row"
    assert result.parsed_sets[0].weight == 140.0


def test_golden_face_pulls(parser):
    result = parser.parse("4 sets of 15 cable face pull with 50 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Cable Face Pull"
    assert result.parsed_sets[0].weight == 50.0


def test_golden_tricep_pushdowns(parser):
    result = parser.parse("3 sets of 12 tricep pushdowns at 60 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Cable Tricep Pushdown"
    assert result.parsed_sets[0].weight == 60.0


def test_golden_leg_press_four_plates(parser):
    result = parser.parse("4 sets of 10 leg press with four plates")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Leg Press"
    assert result.parsed_sets[0].weight == 405.0


def test_golden_leg_extensions(parser):
    result = parser.parse("3 sets of 12 leg extensions at 150 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Leg Extension"
    assert result.parsed_sets[0].weight == 150.0


def test_golden_leg_curls(parser):
    result = parser.parse("3 sets of 12 leg curls at 130 lbs")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Leg Curl"
    assert result.parsed_sets[0].weight == 130.0


def test_golden_three_plates(parser):
    result = parser.parse("1 rep deadlift with three plates")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].weight == 315.0


def test_golden_five_plates(parser):
    result = parser.parse("1 rep deadlift at five plates")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].weight == 495.0


def test_golden_warmup_set(parser):
    result = parser.parse("warmup set of 10 at 135 on bench")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].is_warmup is True
    assert result.parsed_sets[0].exercise_name == "Barbell Bench Press"
    assert result.parsed_sets[0].reps == 10
    assert result.parsed_sets[0].weight == 135.0


def test_golden_by_shorthand(parser):
    result = parser.parse("5 by 10 back squat at 185")
    assert len(result.parsed_sets) == 1
    assert result.parsed_sets[0].exercise_name == "Barbell Back Squat"
    assert result.parsed_sets[0].sets == 5
    assert result.parsed_sets[0].reps == 10
    assert result.parsed_sets[0].weight == 185.0
