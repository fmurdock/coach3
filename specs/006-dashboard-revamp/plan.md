# Implementation Plan: 006-dashboard-revamp

**Branch**: `feature/006-dashboard-revamp` | **Date**: 2026-11-22 | **Spec**: [specs/006-dashboard-revamp/spec.md](spec.md)

**Input**: Feature specification from `specs/006-dashboard-revamp/spec.md`

## Summary

Revamp the Coach3 Training Dashboard to deliver goal-tracked macro cardio and resistance analytics alongside an interactive micro-level workout table and deep telemetry drill-downs. On the macro layer, the top cardio section separates **Zone 2 Cardio** (weekly minutes tracked against a **120 minutes/week** goal line) from **VO2 Max Training** (weekly Zone 5 minutes at $\ge 90\%$ of configured Max HR tracked against a suggested **20 minutes/week** goal line, with weekly **Zone 4** minutes surfaced alongside Zone 5 so hard interval bouts spanning upper Zone 4 and Zone 5 are never hidden), while the resistance volume section focuses strictly on four canonical categories — **Pull, Push, Legs, and Abs** — each measured against a **10 sets/week** target with top working weights and Brzycki estimated 1RM progression (isolating any unmapped exercises under an optional fallback `Other` bucket). All macro views and workout lists respond to quick preset windows (`7d`, `30d`, `90d`, `ytd`, `all`) and a custom `start_date`/`end_date` range selector.

On the micro layer, clicking any session expands an inline detail drawer tailored to session type: strength sessions surface `user_notes` and structured `strength_sets` without blank/synthetic chart canvases, while telemetry-backed cardio sessions display a synchronized dual-axis timeline (Heart Rate bpm + Pace inverted), an optional self-hosted Mercator SVG **Run Route Map** card with GPX upload (`POST /api/v1/workouts/{id}/gpx`), a **Multi-Set Curve Overlay** plotting both Pace and Heart Rate on normalized interval elapsed time, an interval breakdown table including `peak_heart_rate`, and clickable per-interval rows opening an inline `Workout Graph: Interval N` view (Pace, SPM, Heart Rate). Supporting ingestion and profile work aligns Concept2 interval stroke timestamp offsets, Polar GPX/zone ingestion, boundary-safe HR zone classification (`src/services/zone_calculator.py`), and live HR zone calibration (`GET`/`PUT /api/v1/profile/heart-rate`, defaulting new profiles to `max_hr = 185` editable in Settings—never hardcoded—with auto-derive zone support and historical recalculation).

## Technical Context

**Language/Version**: Python 3.12 (backend), HTML5 / Vanilla Modern JavaScript / CSS3 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (asyncio), Pydantic v2, self-hosted Chart.js bundle (`src/static/vendor/chart.umd.js`), Alembic

**Storage**: SQLite / PostgreSQL with SQLAlchemy ORM (`WorkoutSession`, `HeartRateSample`, `WorkoutSplit`, `GPSRoutePoint`, `StrengthSet`, `StrengthExercise`)

**Testing**: pytest, pytest-asyncio, httpx

**Target Platform**: Self-hosted server / Docker container, responsive on modern mobile browsers (iPhone Safari, Android Chrome) down to 375px width and desktop viewports

**Project Type**: Web Application (FastAPI REST backend + responsive static HTML/JS dashboard & configuration UI)

**Performance Goals**: Initial macro dashboard load $< 500\text{ms}$; workout row click, chart expansion, and Mercator route SVG render $< 200\text{ms}$

**Constraints**: Fully self-hosted with zero external analytics tracking, zero third-party chart CDNs, and zero external map tile dependencies (Constitution Principle I); mobile-optimized ergonomics without horizontal scrolling (Constitution Principle III)

**Scale/Scope**: Single athlete / multi-user self-hosted database; handles up to 5,000 workouts and 500k telemetry/GPS samples per user

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Pre-Design / Post-Design Compliance Analysis | Status |
| :--- | :--- | :--- | :--- |
| **I. Self-Hosted Architecture & Data Sovereignty** | Local computation, zero raw telemetry leakage or external third-party runtime dependencies | All aggregation algorithms, dual-axis & per-interval Chart.js rendering (`src/static/vendor/chart.umd.js`), Mercator SVG run route rendering (`GPSRoutePoint`), and HR zone recalculations execute locally on athlete hardware with zero external CDN, map tile, or LLM/analytics API calls. | ✅ PASS |
| **II. Modular Ingestion & Source Isolation** | Keep ingestion decoupled from analytics | Read-only analytics over canonical `workout_sessions`, `heart_rate_samples`, `workout_splits`, `gps_route_points`, and `strength_sets`. Source adapters (`polar.py`, `concept2.py`) normalize vendor data (interval stroke offset alignment, GPX parsing, zone mapping) cleanly before persistence. | ✅ PASS |
| **III. Multimodal Ergonomics & Robustness** | Mobile-first UI, responsive, graceful degradation | Supports 375px+ mobile viewports, suppresses empty/synthetic chart canvases on telemetry-less strength sessions, and provides inline GPX upload fallback when run route data is absent. | ✅ PASS |
| **IV. Unified Volume Modeling & Peak Performance** | Zone 2 & VO2 Max cardio tracking, standardized muscle group sets, deterministic analytics | Tracks weekly Zone 2 (`120 min/wk` goal) and Zone 5 VO2 Max (`20 min/wk` goal) minutes alongside canonical `Push`, `Pull`, `Legs`, and `Abs` weekly working sets (`10 sets/wk` goal) and deterministic Brzycki 1RM estimates. | ✅ PASS |
| **V. Philosophy-Steered Coaching** | Adherence to target training philosophy | Surfaces polarized aerobic base vs. $\ge 90\%$ max HR VO2 Max stimulus ratios, progressive overload metrics, and synchronized HR/pace interval consistency curves directly to the athlete. | ✅ PASS |

**Post-Design Gate Re-Evaluation**: All 5 principles pass after completing Phase 1 schema updates (`data-model.md`, `contracts/api-dashboard.yaml`, `quickstart.md`). No constitutional violations or waivers required.

## Project Structure

### Documentation (this feature)

```text
specs/006-dashboard-revamp/
├── plan.md              # This implementation plan
├── research.md          # Architectural, goal calibration & visualization decisions
├── data-model.md        # Logical entities and Pydantic schemas
├── contracts/
│   └── api-dashboard.yaml # OpenAPI 3.1 specification (v2.0.0) for dashboard, workout, GPX & HR profile endpoints
├── quickstart.md        # End-to-end verification and visual testing instructions
├── checklists/
│   └── requirements.md  # Spec quality validation checklist
└── tasks.md             # Dependency-ordered task list updated via /speckit-tasks
```

### Source Code Layout

```text
src/
├── adapters/
│   ├── concept2.py      # Concept2 stroke/interval timestamp offset alignment & telemetry normalization
│   └── polar.py         # Polar Flow telemetry, HR zone calculation, and GPX route extraction
├── api/
│   ├── analytics.py     # Macro volume endpoints (/api/v1/analytics/dashboard with window & start_date/end_date)
│   ├── profile.py       # HR calibration endpoints (GET/PUT /api/v1/profile/heart-rate) & zone recalculation
│   ├── workouts.py      # Workout list, drill-down detail (/detail), and GPX upload (/gpx)
│   └── router.py        # API router aggregation
├── models/
│   ├── workout.py       # WorkoutSession model
│   ├── telemetry.py     # HeartRateSample, WorkoutSplit, GPSRoutePoint models
│   ├── strength_set.py  # StrengthSet model
│   └── exercise.py      # StrengthExercise model
├── schemas/
│   ├── analytics.py     # Pydantic models for Zone 2 / VO2 Max goals and Pull/Push/Legs/Abs volume
│   └── workout.py       # Pydantic models for table rows, detail drawers, interval splits, and GPX routes
├── services/
│   ├── analytics_service.py # Aggregates Zone 2/4/5 weekly buckets, canonical 4-group resistance sets & 1RM
│   ├── seed_service.py      # Demo seed generator (steady-state runs, GPX points, 4x4 interval row, Push/Pull/Legs/Abs)
│   └── zone_calculator.py   # Boundary-safe Zone 1–5 duration calculator using athlete's configured HR profile
└── static/
    ├── vendor/
    │   └── chart.umd.js # Self-hosted Chart.js bundle (no CDN dependency)
    ├── config.html      # Athlete HR zone & Max HR (185 bpm default) calibration UI with auto-derive helper
    └── dashboard.html   # Responsive dashboard (Zone 2 & VO2 Max/Z4 goal charts, 4-group resistance table, custom dates, drill-down drawers, Run Route SVG)

tests/
├── unit/
│   ├── test_dashboard_analytics.py # Tests for Zone 2/4/5 goals, custom date range & Pull/Push/Legs/Abs volume
│   ├── test_telemetry_drilldown.py # Tests for interval slicing, overlay Pace+HR curves, GPX & HR recalc
│   └── test_zone_calculator.py     # Tests for contiguous & inclusive HR zone boundary classification
└── integration/
    └── test_dashboard_api.py       # End-to-end API contract tests against OpenAPI spec
```

---

## Phases & Implementation Strategy

### Phase 0: Outline & Research *(Complete)*
- Documented architectural decisions in [research.md](research.md):
  - Separated Zone 2 (120 min/wk) and VO2 Max (20 min/wk, $\ge 90\%$ max HR) charts/goals.
  - Canonicalized resistance categories into `Pull`, `Push`, `Legs`, and `Abs` (10 sets/wk goal) with isolated `Other` fallback.
  - Specified dual-axis Chart.js configuration (Pace inverted + HR), Multi-Set Pace+HR overlay, and clickable per-interval `Workout Graph: Interval N` charts (Pace, SPM, Heart Rate).
  - Selected self-hosted Chart.js and local Mercator SVG GPX map rendering to eliminate external CDNs/map tiles.
  - Captured telemetry normalization gaps (Concept2 stroke offset alignment, HR zone profile calibration & recalculation, telemetry-less strength drawer suppression of blank canvases).

### Phase 1: Design & Contracts *(Complete)*
- Updated [data-model.md](data-model.md) with `CardioVolumeSummary`, `WeeklyCardioBucket`, `MuscleGroupVolumeSummary`, `WorkoutTableRow`, `WorkoutDetailTelemetry`, `StrengthSetDetail`, `TelemetryPoint`, `IntervalSplitDetail`, `NormalizedSample`, and `GPSRoutePoint`.
- Updated OpenAPI 3.1 specification (v2.0.0) in [contracts/api-dashboard.yaml](contracts/api-dashboard.yaml) covering `/api/v1/analytics/dashboard`, `/api/v1/workouts`, `/api/v1/workouts/{workout_id}/detail`, `/api/v1/workouts/{workout_id}/gpx`, and `/api/v1/profile/heart-rate`.
- Updated runnable validation steps and curl/UI checks in [quickstart.md](quickstart.md).
- Re-evaluated post-design Constitution Check: all 5 principles pass.

### Phase 2: Next Step (Tasks Generation)
- Proceed to `/speckit-tasks` to regenerate/align actionable, dependency-ordered tasks in [tasks.md](tasks.md) against the updated plan and contracts before executing `/speckit-implement`.
