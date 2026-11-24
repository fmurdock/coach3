# Quickstart: 006-dashboard-revamp

**Feature Branch**: `feature/006-dashboard-revamp`
**Date**: 2026-11-21
**Status**: Ready for Implementation

This guide provides end-to-end verification procedures for testing the revamped Coach3 Training Dashboard, including dedicated Zone 2 and VO2 Max weekly goal charts, canonical Pull/Push/Legs/Abs weekly strength volume tracking, custom date-range filtering, workout detail drawers (strength sets & notes, dual-axis Pace/HR timeline, clickable per-interval graphs, GPX route map), and HR zone calibration.

---

## Prerequisites

1. Activate project virtual environment:
   ```bash
   source .venv/bin/activate
   ```
2. Verify dependencies:
   ```bash
   python -c "import fastapi, sqlalchemy, pydantic; print('Dependencies OK')"
   ```

---

## 1. Seed Multi-Modal Test Data (Including 4x4 Interval Rower)

Run the demo seed script to ensure sample sessions exist across all disciplines, including structured interval rowing and canonical resistance sessions:
```bash
python -m src.scripts.seed_demo
```
Expected seeded coverage:
- Cardio sessions across steady-state runs (with GPS route points) and Concept2 4x4 min interval rowing.
- Strength sets mapped cleanly to canonical `push`, `pull`, `legs`, and `abs` muscle groups.

---

## 2. API Contract Verification

Start the server (`uvicorn src.main:app --host 127.0.0.1 --port 8000`) or verify endpoints using `httpx` / `pytest`:

### A. Verify Macro Volume Endpoint (Preset Window & Custom Date Range)
```bash
curl -s "http://127.0.0.1:8000/api/v1/analytics/dashboard?window=30d" | jq .
curl -s "http://127.0.0.1:8000/api/v1/analytics/dashboard?start_date=2026-11-01&end_date=2026-11-21" | jq .
```
**Expected Response Checks**:
- `cardio.zone2_weekly_goal_minutes == 120.0`
- `cardio.vo2max_weekly_goal_minutes == 20.0`
- `cardio.zone2_minutes >= 0` and `cardio.zone5_minutes >= 0`
- `cardio.weekly_buckets` provides weekly Zone 2 (`zone2_minutes`) and Zone 5 (`zone5_minutes`) breakdowns.
- `resistance` contains canonical entries for `push`, `pull`, `legs`, and `abs` with `weekly_goal_sets == 10.0`, `working_sets`, `top_weight_lbs`, and `estimated_1rm_lbs` (with any unmapped fallback grouped into `other`).

### B. Verify Workout Table Endpoint
```bash
curl -s "http://127.0.0.1:8000/api/v1/workouts?limit=10" | jq '.[0]'
```
**Expected Response Checks**:
- Each `WorkoutTableRow` contains `id`, `discipline`, `title`, `duration_sec`, `primary_metric_label`, `has_telemetry`, and `is_interval_workout`.

### C. Verify Workout Detail Drill-Downs (Cardio Intervals, GPX Route, Strength)
Find the ID of the 4x4 min interval row session and inspect its detail payload:
```bash
ROW_ID=$(curl -s "http://127.0.0.1:8000/api/v1/workouts?discipline=indoor_row" | jq -r '.[0].id')
curl -s "http://127.0.0.1:8000/api/v1/workouts/${ROW_ID}/detail" | jq .
```
**Expected Response Checks**:
- `time_series`: Non-empty array of `TelemetryPoint` records (`elapsed_sec`, `heart_rate`, `pace_sec`).
- `splits`: `IntervalSplitDetail` rows including `peak_heart_rate` and interval timing aligned cleanly against stroke timestamps.
- `interval_consistency`: Contains `superimposed_curves` (`NormalizedSample`) plotting both Pace and Heart Rate on normalized interval elapsed time (`0` to interval duration) for every work interval.
- **Strength drill-down**: Querying `/api/v1/workouts/{strength_id}/detail` returns `user_notes` and structured `strength_sets` (`StrengthSetDetail`), without requiring synthetic telemetry.
- **GPX Route Upload**:
  ```bash
  curl -s -X POST "http://127.0.0.1:8000/api/v1/workouts/${RUN_ID}/gpx" \
    -F "file=@sample_route.gpx" | jq .
  ```
  Verify `GET /api/v1/workouts/${RUN_ID}/detail` subsequently includes populated `GPSRoutePoint` route coordinates.

### D. Verify HR Profile Calibration (Default 185 bpm) & Boundary-Safe Recalculation
```bash
curl -s "http://127.0.0.1:8000/api/v1/profile/heart-rate" | jq .
curl -s -X PUT "http://127.0.0.1:8000/api/v1/profile/heart-rate" \
  -H "Content-Type: application/json" \
  -d '{"resting_hr": 55, "max_hr": 185, "zone1_min": 93, "zone1_max": 111, "zone2_min": 111, "zone2_max": 130, "zone3_min": 130, "zone3_max": 148, "zone4_min": 148, "zone4_max": 167, "zone5_min": 167, "zone5_max": 185}' | jq .
```
**Expected Response Checks**:
- New profiles default to `max_hr == 185` (never hardcoded in analytics).
- Updating Max HR / Zone 1–5 thresholds recalculates all historical workouts without dropping boundary BPM samples (works for both contiguous `148–167 / 167–185` and inclusive `148–166 / 167–185` bounds) and immediately updates Zone 2, Zone 4, and Zone 5 totals on `/api/v1/analytics/dashboard`.

---

## 3. UI Visual Verification

1. Start the application:
   ```bash
   uvicorn src.main:app --host 127.0.0.1 --port 8000
   ```
2. Open browser to `http://127.0.0.1:8000/dashboard`:
   - **Custom Date-Range Selector**: Verify preset windows (`7d`, `30d`, `90d`) plus custom `start_date`/`end_date` date inputs dynamically refresh both macro charts, resistance goal table, and workouts list.
   - **Zone 2 Cardio Chart**: Verify weekly Zone 2 minutes render against the **120 min/week** goal line.
   - **VO2 Max Training Chart**: Verify weekly Zone 5 minutes render against the **20 min/week** goal line.
   - **Resistance Volume Table**: Verify rows cover **Pull**, **Push**, **Legs**, and **Abs** with weekly set counts measured against the **10 sets/week** goal, top working weight, and estimated 1RM progression.
   - **Strength Drill-Down**: Click any resistance workout row; verify `user_notes` and structured `strength_sets` render cleanly with **no blank telemetry canvas**.
   - **Cardio & GPX Route Card**: Click a run workout with GPX coordinates; verify dual-axis chart (HR bpm + Pace inverted) and self-hosted Mercator SVG **Run Route Map** card (or inline GPX upload affordance when route data is missing).
   - **Multi-Set Overlay & Per-Interval Graph**: Click the 4x4 min Concept2 row workout. Verify the Multi-Set Curve Overlay plots both Pace and Heart Rate curves across normalized interval time, the interval breakdown table includes `peak_heart_rate`, and clicking an interval row opens the inline `Workout Graph: Interval N` chart (Pace, SPM, Heart Rate).
3. Open `http://127.0.0.1:8000/config` to verify HR zone thresholds synchronize with `/api/v1/profile/heart-rate`.

---

## 4. Automated Regression Tests

Run full test suite:
```bash
.venv/bin/pytest tests/unit/ tests/integration/
```
Ensure 100% passing tests with zero regressions.
