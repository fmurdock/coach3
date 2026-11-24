# Data Model: 006-dashboard-revamp

**Feature Branch**: `feature/006-dashboard-revamp`
**Date**: 2026-11-20 (Updated 2026-11-21)
**Status**: Ready for Implementation

## Overview

This document specifies the logical domain entities, response schemas, and validation rules for the Coach3 Training Dashboard, covering split Zone 2 and VO2 Max (with Zone 4 visibility) weekly goal tracking, Push/Pull/Legs/Abs weekly set tracking, full workout drill-down telemetry (including notes, strength sets, route geometry, and per-interval charts), and configurable athlete heart rate profile synchronization (defaulting to `185 bpm` Max HR, never hardcoded).

### Conceptual Entity-to-Schema Mapping (`spec.md` → Pydantic)

| `spec.md` Key Entity | Concrete Schema(s) |
| :--- | :--- |
| `Zone2CardioSummary` / `VO2MaxSummary` | `CardioVolumeSummary` + `WeeklyCardioBucket` |
| `StrengthCategoryVolumeSummary` | `MuscleGroupVolumeSummary` |
| `WorkoutDetailView` | `WorkoutDetailTelemetry` + `StrengthSetDetail` |
| `IntervalOverlayDataset` | `IntervalConsistencyAnalysis` + `NormalizedSample` |
| `RunRouteTrack` | `GPSRoutePointSchema` (`GPSRoutePoint` ORM) |
| `HeartRateZoneProfile` | `HeartRateProfileRequest` / `HeartRateProfileResponse` (`UserHeartRateProfile` ORM) |

---

## Entities & Schemas

### 1. `CardioVolumeSummary` & `WeeklyCardioBucket`
Aggregated cardiovascular volume tracking Zone 2 aerobic base (`120 min/wk` target) and VO2 Max Zone 5 intensity (`20 min/wk` suggested target) alongside Zone 4 threshold visibility.

| Field | Type | Description |
| :--- | :--- | :--- |
| `total_cardio_minutes` | `float` | Cumulative cardio duration across outdoor run, indoor row, erg bike |
| `zone2_minutes` | `float` | Cumulative minutes in Zone 2 aerobic base |
| `zone4_minutes` | `float` | Cumulative minutes in Zone 4 (80–90% of configured Max HR) |
| `zone5_minutes` | `float` | Cumulative minutes in Zone 5 ($\ge 90\%$ of configured Max HR) dedicated VO2 max stimulus |
| `zone2_percentage` | `float` | Ratio of Zone 2 to total cardio duration |
| `zone5_percentage` | `float` | Ratio of Zone 5 to total cardio duration |
| `zone2_weekly_goal_minutes` | `float` | Weekly Zone 2 target (`120.0` default) |
| `vo2max_weekly_goal_minutes` | `float` | Weekly VO2 Max target (`20.0` suggested default) |
| `zone2_avg_weekly_minutes` | `float` | Average Zone 2 minutes per week in active window |
| `zone4_avg_weekly_minutes` | `float` | Average Zone 4 minutes per week in active window |
| `vo2max_avg_weekly_minutes` | `float` | Average VO2 Max (Zone 5) minutes per week in active window |
| `weekly_trend` | `List[WeeklyCardioBucket]` | Chronological weekly buckets |

#### `WeeklyCardioBucket`
| Field | Type | Description |
| :--- | :--- | :--- |
| `week_label` | `str` | Week start label (e.g., `"Nov 17"`) |
| `miles` | `float` | Weekly cardio distance in miles |
| `zone2_hours` | `float` | Weekly Zone 2 hours (legacy compatibility) |
| `zone2_minutes` | `float` | Exact weekly Zone 2 minutes |
| `zone4_minutes` | `float` | Weekly Zone 4 (threshold / high-intensity) minutes |
| `zone5_minutes` | `float` | Weekly Zone 5 (VO2 Max) minutes |

---

### 2. `MuscleGroupVolumeSummary` (Strength Category Tracking)
Tracks working set volume against a **10 sets/week** goal across **Push, Pull, Legs, and Abs** (plus **Other** fallback when unmapped working sets exist).

| Field | Type | Description |
| :--- | :--- | :--- |
| `muscle_group` | `str` | Canonical slug: `push`, `pull`, `legs`, `abs` (or `other` when unassigned) |
| `display_name` | `str` | Display label: `"Push"`, `"Pull"`, `"Legs"`, `"Abs"`, `"Other"` |
| `working_sets` | `int` | Total completed non-warmup working sets in period |
| `weekly_avg_sets` | `float` | Average working sets per week across the active window |
| `weekly_goal_sets` | `float` | Target weekly sets per category (`10.0` for Push/Pull/Legs/Abs; `0.0` for Other) |
| `goal_progress_pct` | `float` | Percentage of weekly target achieved (`weekly_avg_sets / weekly_goal_sets * 100`) |
| `total_reps` | `int` | Total completed working repetitions |
| `top_exercise_name` | `str | None` | Exercise name of heaviest working set |
| `top_weight_lbs` | `float | None` | Heaviest working weight in lbs |
| `top_reps` | `int | None` | Repetitions on heaviest working set |
| `estimated_1rm_lbs` | `float | None` | Peak estimated 1RM via Brzycki formula |

---

### 3. `WorkoutTableRow`
Summary row projection for chronological display in Recent Workouts.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Canonical session ID |
| `discipline` | `str` | `outdoor_run`, `indoor_row`, `erg_bike`, `strength` |
| `title` | `str` | Athlete-facing workout title |
| `start_time_utc` | `datetime` | True UTC session start timestamp |
| `duration_sec` | `float` | Workout duration in seconds |
| `distance_m` | `float | None` | Distance in meters |
| `avg_heart_rate` | `int | None` | Session average HR |
| `max_heart_rate` | `int | None` | Session max HR |
| `primary_metric_label` | `str` | Highlight summary metric |
| `has_telemetry` | `bool` | True if continuous telemetry exists |
| `is_interval_workout` | `bool` | True when session has $\ge 2$ work intervals |

---

### 4. `WorkoutDetailTelemetry`
Full workout drill-down payload returned on row expansion.

| Field | Type | Description |
| :--- | :--- | :--- |
| `workout_id` | `UUID` | Session ID |
| `discipline` | `str | None` | Modality |
| `title` | `str | None` | Session title |
| `user_notes` | `str | None` | Athlete notes / commentary |
| `total_duration_sec` | `float | None` | Duration in seconds |
| `total_distance_m` | `float | None` | Distance in meters |
| `total_calories` | `int | None` | Active calories |
| `avg_heart_rate` | `int | None` | Average BPM |
| `max_heart_rate` | `int | None` | Peak BPM |
| `avg_pace_sec_per_km` | `float | None` | Average pace (sec/km) |
| `elevation_gain_m` | `float | None` | Cumulative climb (meters) |
| `elevation_loss_m` | `float | None` | Cumulative descent (meters) |
| `rest_distance_m` | `float | None` | Rest/recovery distance (Concept2 intervals) |
| `hr_zone_seconds` | `dict[str, float] | None` | Recorded seconds in `zone1..zone5` |
| `time_series` | `List[TelemetryPoint]` | Continuous samples (empty for strength / telemetry-less workouts) |
| `splits` | `List[IntervalSplitDetail]` | Ordered work intervals / laps and between-set rests |
| `strength_sets` | `List[StrengthSetDetail]` | Structured resistance sets (exercise, set #, reps, weight, RPE, warmup flag) |
| `route_points` | `List[GPSRoutePointSchema]` | Chronological GPS route coordinates |
| `interval_consistency` | `IntervalConsistencyAnalysis | None` | Superimposed Pace + HR curve overlays and variance % |

#### `StrengthSetDetail`
- `exercise_name`: `str`
- `category`: `str` (`push`, `pull`, `legs`, `abs`, `other`)
- `set_index`: `int`
- `reps_completed`: `int`
- `weight_lbs`: `float`
- `is_bodyweight`: `bool`
- `added_weight_lbs`: `float | None`
- `rpe`: `float | None`
- `is_warmup`: `bool`

#### `TelemetryPoint`
- `elapsed_sec`: `float` (cumulative seconds across work + rest)
- `heart_rate`: `int | None`
- `pace_sec`: `float | None`
- `power_watts`: `float | None`
- `cadence_spm`: `float | None`

#### `IntervalSplitDetail` & `NormalizedSample`
- `split_index`, `split_type` (`interval`, `work`, `lap`, `rest`), `duration_sec`, `distance_m`, `avg_heart_rate`, `ending_heart_rate`, `peak_heart_rate`, `avg_pace_sec`, `avg_power_watts`, `avg_cadence_spm`, and `samples: List[NormalizedSample]` (`set_elapsed_sec`, `heart_rate`, `pace_sec`, `cadence_spm`).
