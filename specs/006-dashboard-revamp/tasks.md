---

description: "Actionable, dependency-ordered task list for implementing the revamped Coach3 Training Dashboard"
---

# Tasks: 006-dashboard-revamp

**Input**: Design documents from `specs/006-dashboard-revamp/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/api-dashboard.yaml`, `quickstart.md`)

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/api-dashboard.yaml`

**Tests**: Unit tests (`tests/unit/`) and integration contract tests (`tests/integration/`) are included for every user story.

**Organization**: Tasks are grouped by user story (`US1`, `US2`, `US3`) to enable independent implementation and verification. Previously completed baseline tasks are marked `[X]`; remaining revamp and convergence tasks are marked `[ ]`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, self-hosted static assets, and multi-modal demo fixtures

- [X] T001 [P] Verify Python 3.12 dependencies in `.venv` and self-hosted Chart.js bundle at `src/static/vendor/chart.umd.js` wired into `src/static/dashboard.html`
- [X] T002 [P] Update demo seed generator in `src/services/seed_service.py` to seed a 4x4 min Concept2 interval rower workout with work/rest splits and per-interval telemetry samples
- [X] T003 [P] Align demo seed strength exercises and outdoor run GPS fixtures in `src/services/seed_service.py` so seeded workouts cover `push`, `pull`, `legs`, `abs`, steady-state `GPSRoutePoint` tracks, and realistic `user_notes`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Canonical Pydantic schemas, 4-category muscle classifier, ingestion alignment, and HR profile synchronization that MUST be complete before story-level revamp work

⚠️ **CRITICAL**: No pending User Story work (`T013+`, `T021+`, `T028+`) should proceed until `T008`–`T010` are complete.

- [X] T004 [P] Create baseline Pydantic v2 macro dashboard schemas in `src/schemas/analytics.py`
- [X] T005 [P] Create baseline Pydantic v2 workout table and drill-down schemas (`WorkoutTableRow`, `WorkoutDetailTelemetry`, `TelemetryPoint`, `IntervalSplitDetail`, `IntervalConsistencyAnalysis`, `GPSRoutePointSchema`, `user_notes`) in `src/schemas/workout.py`
- [X] T006 [P] Implement `AnalyticsService.calculate_estimated_1rm` (Brzycki formula) and `resolve_date_window` in `src/services/analytics_service.py`
- [X] T007 Implement Polar GPX/zone ingestion (`src/adapters/polar.py`), Concept2 interval stroke timestamp offset alignment (`src/adapters/concept2.py`), and `GET`/`PUT /api/v1/profile/heart-rate` historical recalculation (`src/api/profile.py`, `src/static/config.html`)
- [X] T008 [P] Update `CardioVolumeSummary`, `WeeklyCardioBucket`, and `MuscleGroupVolumeSummary` in `src/schemas/analytics.py` per `data-model.md` and `contracts/api-dashboard.yaml`: add `zone2_weekly_goal_minutes: float = 120.0`, `vo2max_weekly_goal_minutes: float = 20.0`, `zone2_avg_weekly_minutes: float = 0.0`, `vo2max_avg_weekly_minutes: float = 0.0`, `WeeklyCardioBucket.zone2_minutes: float = 0.0`, `weekly_avg_sets: float = 0.0`, `weekly_goal_sets: float = 10.0`, `goal_progress_pct: float = 0.0`, and restrict `muscle_group` categories to `[push, pull, legs, abs, other]`
- [X] T009 [P] Add `StrengthSetDetail` (`exercise_name: str`, `category: str`, `set_index: int`, `reps_completed: int`, `weight_lbs: float`, `is_bodyweight: bool`, `added_weight_lbs: float | None = None`, `rpe: float | None = None`, `is_warmup: bool = False`) and attach `strength_sets: list[StrengthSetDetail] = []` to `WorkoutDetailTelemetry` in `src/schemas/workout.py`
- [X] T010 Update `AnalyticsService.normalize_muscle_group` in `src/services/analytics_service.py` (depends on `T008`) to map strength exercises exclusively into canonical `("push", "Push")`, `("pull", "Pull")`, `("legs", "Legs")`, and `("abs", "Abs")` buckets using keyword/muscle metadata rules, routing unmapped/null inputs to `("other", "Other")` instead of `"Back"`
- [X] T035 [P] Fix boundary-BPM classification in `src/services/zone_calculator.py` to evaluate zones top-down (`bpm >= zone5_min` → `zone4_min` → `zone3_min` → `zone2_min` → `zone1_min`) so both contiguous (`148–167` / `167–185`) and inclusive non-overlapping (`148–166` / `167–185`) HR bounds classify every sample `>= zone1_min` with zero dropped boundary readings (`FR-016`)
- [X] T036 [P] Update default new-profile initialization in `src/api/profile.py` and `src/services/seed_service.py` to default `max_hr = 185` (`Z1: 93–111`, `Z2: 111–130`, `Z3: 130–148`, `Z4: 148–167`, `Z5: 167–185`) without hardcoding `185` into any zone or analytics calculation (`FR-005`)
- [X] T037 [P] Add `zone4_minutes: float = 0.0` and `zone4_avg_weekly_minutes: float = 0.0` to `CardioVolumeSummary` and `zone4_minutes: float = 0.0` to `WeeklyCardioBucket` in `src/schemas/analytics.py` per `data-model.md` and `contracts/api-dashboard.yaml` (`FR-002`)

**Checkpoint**: Foundational schemas and canonical Push/Pull/Legs/Abs classification are ready — user stories can now proceed.

---

## Phase 3: User Story 1 - Macro-Level Volume & Weekly Goal Command Center (Priority: P1) 🎯 MVP

**Goal**: Display two dedicated macro cardio charts — **Zone 2 Cardio** (vs **120 minutes/week** goal) and **VO2 Max Training** (Zone 5 $\ge 90\%$ max HR vs **20 minutes/week** goal) — alongside a streamlined **Pull / Push / Legs / Abs** strength breakdown (**10 sets/week** goal each) and full preset + custom date-range filtering (`start_date`/`end_date`).

**Independent Test**: Call `GET /api/v1/analytics/dashboard?window=30d` and `?start_date=...&end_date=...` and inspect `/dashboard` to verify separate Zone 2 (120m/wk line) and VO2 Max (20m/wk line) charts plus Push/Pull/Legs/Abs weekly set progress against 10 sets/week.

### Tests for User Story 1

- [X] T011 [P] [US1] Create baseline unit and integration tests for macro dashboard analytics in `tests/unit/test_dashboard_analytics.py` and `tests/integration/test_dashboard_api.py`
- [X] T013 [P] [US1] Expand unit and integration tests in `tests/unit/test_dashboard_analytics.py` and `tests/integration/test_dashboard_api.py` to assert `zone2_weekly_goal_minutes == 120.0`, `vo2max_weekly_goal_minutes == 20.0`, weekly `zone2_minutes` vs `zone5_minutes` buckets, canonical `push`/`pull`/`legs`/`abs` (`weekly_goal_sets == 10.0`) + conditional `other` (`weekly_goal_sets == 0.0`, omitted when 0 sets), and custom `start_date`/`end_date` queries
- [X] T038 [P] [US1] Add unit and integration tests in `tests/unit/test_zone_calculator.py`, `tests/unit/test_dashboard_analytics.py`, and `tests/integration/test_dashboard_api.py` verifying inclusive & contiguous HR boundary classification, default `max_hr == 185` profile initialization + live recalculation, and Zone 4 + Zone 5 macro payload fields

### Implementation for User Story 1

- [X] T012 [US1] Register `GET /api/v1/analytics/dashboard` in `src/api/analytics.py` delegating window resolution to `AnalyticsService.resolve_date_window`
- [X] T014 [US1] Update `AnalyticsService.get_macro_dashboard_volume` in `src/services/analytics_service.py` (depends on `T008`, `T010`) to compute `WeeklyCardioBucket.zone2_minutes`, `zone2_avg_weekly_minutes` (`zone2_weekly_goal_minutes = 120.0`), and `vo2max_avg_weekly_minutes` (`vo2max_weekly_goal_minutes = 20.0`), and aggregate non-warmup working sets into always-present `push`, `pull`, `legs`, `abs` entries (`weekly_goal_sets = 10.0`, `weekly_avg_sets`, `goal_progress_pct`) plus conditional `other` (`weekly_goal_sets = 0.0`) only when unmapped `working_sets > 0`
- [X] T015 [US1] Replace the unified cardio macro card in `src/static/dashboard.html` (depends on `T014`) with two separate charts: **Zone 2 Cardio** (weekly Zone 2 minutes + dashed `120 min/wk` target line) and **VO2 Max Training** (weekly Zone 5 $\ge 90\%$ max HR minutes + dashed `20 min/wk` target line)
- [X] T016 [US1] Update the Resistance Training Volume card in `src/static/dashboard.html` (depends on `T014`) to render strictly **Pull, Push, Legs, and Abs** (plus fallback **Other** only when non-zero) showing weekly set counts vs **10 sets/week** goal progress bars, top working set highlights, and estimated 1RM progression
- [X] T017 [US1] Add custom `start_date` and `end_date` inputs alongside preset timeframe buttons (`7d`, `30d`, `90d`, `ytd`, `all`) in `src/static/dashboard.html` triggering synchronized reloads of `/api/v1/analytics/dashboard` and `/api/v1/workouts`, plus clear empty-state prompts linking to `src/static/config.html`
- [X] T039 [US1] Update `AnalyticsService.get_macro_dashboard_volume` in `src/services/analytics_service.py` (depends on `T037`) to compute `CardioVolumeSummary.zone4_minutes`, `zone4_avg_weekly_minutes`, and `WeeklyCardioBucket.zone4_minutes`
- [X] T040 [US1] Update the **VO2 Max Training** card in `src/static/dashboard.html` (depends on `T039`) to display weekly Zone 5 (VO2 Max) and Zone 4 (Threshold / High-Intensity) minutes with distinct colors/legend alongside the dashed `20 min/wk` Zone 5 goal line and summary pills
- [X] T041 [US1] Add an "Auto-fill Zones from Max HR" control (50/60/70/80/90% calculation from the athlete's editable Max HR input, defaulting to `185 bpm`) in `src/static/config.html` (depends on `T036`) saving via `PUT /api/v1/profile/heart-rate` and recalculating historical workout zones

**Checkpoint**: User Story 1 is independently functional and testable as the revamped MVP Command Center.

---

## Phase 4: User Story 2 - Recent Workouts Table, Telemetry Drill-Down & Run Route Card (Priority: P1)

**Goal**: Provide a chronological workouts table (supporting `start_date`/`end_date` filters) whose expandable detail drawers show: synchronized dual-axis HR + Pace timeline and self-hosted Mercator SVG **Run Route Map** card (plus GPX upload) for cardio sessions, and athlete `user_notes` + structured working-set tables without blank/synthetic chart canvases for resistance or telemetry-less sessions.

**Independent Test**: Click an outdoor run row, an indoor row, and a strength workout row in `/dashboard`. Verify cardio drawers show dual-axis telemetry and GPX route SVG (or GPX import button), while strength drawers display `user_notes` and working sets with zero blank chart canvas.

### Tests for User Story 2

- [X] T018 [P] [US2] Create baseline integration tests for `GET /api/v1/workouts` and `GET /api/v1/workouts/{workout_id}/detail` in `tests/integration/test_dashboard_api.py`
- [X] T021 [P] [US2] Add unit and integration tests in `tests/unit/test_telemetry_drilldown.py` and `tests/integration/test_dashboard_api.py` verifying `start_date`/`end_date` filtering on `GET /api/v1/workouts`, populated `strength_sets` + `user_notes` with empty `time_series` (no synthetic HR line) for strength workouts, and `POST /api/v1/workouts/{workout_id}/gpx` route attachment

### Implementation for User Story 2

- [X] T019 [US2] Implement `GET /api/v1/workouts`, `GET /api/v1/workouts/{workout_id}/detail`, and `POST /api/v1/workouts/{workout_id}/gpx` endpoints in `src/api/workouts.py`
- [X] T020 [US2] Implement the Recent Workouts table, accordion drawer, synchronized dual-axis Chart.js timeline (HR + inverted Pace with `/km` and `/mi` tooltips), and self-hosted Mercator SVG **Run Route Map** card with inline GPX upload in `src/static/dashboard.html`
- [X] T022 [US2] Add `start_date: Optional[date]` and `end_date: Optional[date]` query parameters to `GET /api/v1/workouts` in `src/api/workouts.py` using `AnalyticsService.resolve_date_window` per `contracts/api-dashboard.yaml`
- [X] T023 [US2] Update `AnalyticsService.get_workout_detail_telemetry` in `src/services/analytics_service.py` (depends on `T009`, `T010`) to query joined `StrengthSet` + `StrengthExercise` rows, populate `strength_sets` (`StrengthSetDetail` with normalized `push`/`pull`/`legs`/`abs`/`other` categories) and `user_notes`, and keep `time_series == []` without injecting synthetic flat HR data when continuous telemetry is absent
- [X] T024 [US2] Update the workout detail drawer renderer in `src/static/dashboard.html` (depends on `T023`) to hide the telemetry chart `<canvas>` container whenever `time_series.length === 0` (and no telemetry splits exist), display formatted `user_notes`, and render a structured working-set table (`Exercise`, `Category`, `Set`, `Reps`, `Weight`, `RPE`, warmup badge)

**Checkpoint**: User Stories 1 and 2 work independently end-to-end across cardio runs, ergs, and strength sessions.

---

## Phase 5: User Story 3 - Multi-Set Interval Consistency Analyzer & Per-Interval Graphs (Priority: P2)

**Goal**: Enable structured interval workouts (e.g. 4x4 min Concept2 row) to display accurate cumulative timelines across rest gaps, a superimposed **Pace + Heart Rate** Multi-Set Curve Overlay (`0:00` to interval duration), a complete interval breakdown table with `peak_heart_rate`, and clickable rows opening inline `Workout Graph: Interval N` charts (Pace, SPM, Heart Rate).

**Independent Test**: Expand the 4x4 min Concept2 row session in `/dashboard`, toggle to **Multi-Set Curve Overlay** to verify both Pace and HR traces for Intervals 1–4, verify `peak_heart_rate` in the breakdown table, and click an interval row to inspect its `Workout Graph: Interval N` chart.

### Tests for User Story 3

- [X] T025 [P] [US3] Create unit tests in `tests/unit/test_telemetry_drilldown.py` verifying interval slicing, cumulative stroke offset alignment, rest omission after final interval, and pacing variance metrics
- [X] T028 [P] [US3] Extend `tests/unit/test_telemetry_drilldown.py` to assert superimposed overlay curves expose both `pace_sec` and `heart_rate` samples per set and every interval `IntervalSplitDetail` includes `peak_heart_rate` and normalized `samples` (`set_elapsed_sec`, `heart_rate`, `pace_sec`, `cadence_spm`)

### Implementation for User Story 3

- [X] T026 [US3] Implement interval slicing, trailing-rest omission, normalized per-interval `samples`, `peak_heart_rate`, and superimposed consistency curves in `src/services/analytics_service.py` and `src/api/workouts.py`
- [X] T027 [US3] Implement clickable split/interval rows expanding inline `Workout Graph: Interval N` (inverted Pace, Stroke Rate SPM, Heart Rate) in `src/static/dashboard.html`
- [X] T029 [US3] Update `renderOverlayChart` in `src/static/dashboard.html` (depends on `T028`) to plot superimposed **Pace (inverted secondary Y-axis)** alongside **Heart Rate (primary Y-axis)** traces across all work sets (`1..N`) on normalized `set_elapsed_sec` (`0:00` to work duration) with metric toggle/legend clarity
- [X] T030 [US3] Update `renderSplitsTable` in `src/static/dashboard.html` to display `peak_heart_rate` cleanly alongside `avg_heart_rate` and `ending_heart_rate` for every work interval/split row

**Checkpoint**: All three user stories (`US1`, `US2`, `US3`) are complete and independently verifiable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mobile viewport responsiveness, documentation alignment, quickstart walkthrough, and full test suite pass

- [X] T031 [P] Enforce top navigation shell (`Gym Mode`, `Dashboard`, `AI Coach`, `Settings`) and baseline responsive styles across `src/static/dashboard.html` and `src/static/config.html`
- [X] T032 [P] Audit mobile layout at `375px` viewport width in `src/static/dashboard.html` ensuring Zone 2 & VO2 Max goal cards, Push/Pull/Legs/Abs weekly table, custom date-range pickers, strength set drawers, and overlay charts render cleanly with zero horizontal page overflow
- [X] T033 [P] Verify end-to-end API, UI, GPX upload, and HR profile calibration checks documented in `specs/006-dashboard-revamp/quickstart.md`
- [X] T034 Execute full automated test suite via `.venv/bin/pytest tests/` and verify 100% passing tests with zero regressions
- [X] T042 Execute full regression test suite via `.venv/bin/pytest tests/` and verify inline JavaScript syntax in `src/static/dashboard.html` and `src/static/config.html` after HR zone & VO2 Max updates

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: `T001`, `T002` complete; `T003` can run independently or alongside Phase 2.
- **Foundational (Phase 2)**: `T008`, `T009` can run in parallel; `T010` depends on `T008` (`muscle_group` enums) and blocks pending US1 & US2 backend tasks.
- **User Story 1 (Phase 3 - P1 MVP)**: `T013`–`T017` depend on `T008` and `T010`. `T015`, `T016`, `T017` follow `T014` (`src/api/analytics.py` / `src/services/analytics_service.py` payload shape).
- **User Story 2 (Phase 4 - P1)**: `T022` can run immediately (`src/api/workouts.py`); `T023` depends on `T009`, `T010`; `T024` depends on `T023`.
- **User Story 3 (Phase 5 - P2)**: `T028`–`T030` extend existing interval drill-down (`T025`–`T027`) cleanly without blocking US1/US2.
- **Polish (Phase 6)**: `T032`–`T034` run once US1–US3 implementation tasks complete.

### User Story Dependencies

- **US1 (Macro Zone 2 / VO2 Max & Pull/Push/Legs/Abs)**: Independent of US2 and US3 once Phase 2 schemas/classifier (`T008`, `T010`) land.
- **US2 (Workouts Table, Strength Notes/Sets & Run Route Map)**: Independent of US1; shares `resolve_date_window` (`T006`) and canonical categories (`T010`).
- **US3 (Interval Overlay Pace+HR & Per-Interval Graphs)**: Builds on US2's `WorkoutDetailTelemetry` accordion drawer (`src/static/dashboard.html`).

---

## Parallel Examples

```bash
# Phase 2 schema & seed tasks (different files, can run concurrently):
Task: "T003 Align demo seed fixtures in src/services/seed_service.py"
Task: "T008 Update CardioVolumeSummary & MuscleGroupVolumeSummary in src/schemas/analytics.py"
Task: "T009 Add StrengthSetDetail to WorkoutDetailTelemetry in src/schemas/workout.py"

# Cross-story API endpoints & tests after Phase 2:
Task: "T013 [US1] Expand macro analytics unit & integration tests"
Task: "T021 [US2] Add workout filter, strength drawer & GPX tests"
Task: "T022 [US2] Add start_date/end_date params to GET /api/v1/workouts in src/api/workouts.py"
Task: "T028 [US3] Extend interval consistency tests in tests/unit/test_telemetry_drilldown.py"
```

---

## Implementation Strategy

### Incremental Delivery

1. **Foundation (`T003`, `T008`–`T010`)**: Finalize updated Pydantic contracts and switch exercise grouping to strict `Push / Pull / Legs / Abs` + `Other` fallback.
2. **MVP (`T013`–`T017`) — User Story 1**: Ship separate **Zone 2 Cardio** (`120 min/wk`) and **VO2 Max Training** (`20 min/wk`) goal charts, `Push/Pull/Legs/Abs` (`10 sets/wk`) table, and custom date selector. Validate independently via `/api/v1/analytics/dashboard`.
3. **Drill-Down Completeness (`T021`–`T024`) — User Story 2**: Wire date filtering on `/api/v1/workouts` and fix strength workout drawers (`user_notes` + `strength_sets`, suppressing blank canvases).
4. **Interval Polish (`T028`–`T030`) — User Story 3**: Add inverted Pace overlay curves alongside HR in `renderOverlayChart` and surface `peak_heart_rate` in `renderSplitsTable`.
5. **Verification (`T032`–`T034`)**: Audit `375px` mobile ergonomics, run `quickstart.md` verification steps, and pass full `.venv/bin/pytest tests/`.

---

## Notes

- Tasks marked `[X]` reflect baseline and prior telemetry fixes already present in the repository; verify any overlapping tests during `T013`, `T021`, `T028`, and `T034`.
- `[P]` indicates safe parallelism across separate files with no unmet upstream dependencies.
- Preserve strict `src/static/vendor/chart.umd.js` self-hosting and local Mercator SVG rendering (zero external map-tile or CDN requests per Constitution Principle I).
