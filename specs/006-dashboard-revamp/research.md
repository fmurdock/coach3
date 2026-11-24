# Research: 006-dashboard-revamp

**Feature Branch**: `feature/006-dashboard-revamp`
**Date**: 2026-11-20 (Updated 2026-11-21)
**Status**: Completed

## Executive Summary

This document establishes the architectural, visualization, and algorithmic decisions for the revamped Coach3 Training Dashboard: dedicated **Zone 2 Cardio** (120 min/week goal) and **VO2 Max Training** (20 min/week goal) macro charts, streamlined **Push / Pull / Legs / Abs** strength tracking (10 sets/week per category + isolated **Other** fallback), synchronized dual-axis workout drill-downs, self-hosted **Run Route Map** SVG visualization, multi-set **Pace + Heart Rate** consistency overlays, clickable single-interval **Pace / SPM / HR** inline charts, and calibrated wearable Heart Rate Zone synchronization.

---

## Technical Investigations & Decisions

### 1. Split Cardio Macro Charts (Zone 2 vs. VO2 Max Weekly Goals)

- **Context**: Combining Zone 2 minutes and VO2 Max (Zone 5) minutes on a single shared bar chart obscured VO2 Max scale (15–25 min bars dwarfed next to 120–180 min Zone 2 bars) and lacked weekly goal reference lines.
- **Decision**:
  - Render two separate macro cardio cards/charts:
    1. **Zone 2 Cardio Volume**: Weekly accumulated Zone 2 minutes plotted alongside a dashed **120 min/week** goal line and weekly progress summary.
    2. **VO2 Max Training**: Weekly accumulated Zone 5 ($\ge 90\%$ of configured Max HR) minutes plotted alongside a dashed **20 min/week** goal line, **stacked/paired with Zone 4 (80–90% of configured Max HR) minutes** so hard interval bouts (such as 4×4 min sessions spanning upper Zone 4 and Zone 5) remain clearly visible rather than appearing as `0m`.
- **Rationale**: Under an ~80/20–85/15 polarized training model anchored by 120 minutes/week of aerobic Zone 2 work, **20 minutes/week** of Zone 5 stimulus corresponds to ~1–2 high-intensity interval workouts (e.g., 4x4 min bouts) without distorting the Zone 2 scale.
- **Alternatives Considered**:
  - *Dual-series stacked/grouped bar chart*: Makes Zone 5 bars visually tiny next to Zone 2 totals and prevents independent goal lines.

---

### 2. Streamlined Strength Tracking (`Pull`, `Push`, `Legs`, `Abs` + `Other` Fallback)

- **Context**: A 7-muscle-group table fragments compound lifting stimulus (e.g. separating chest, triceps, and anterior delts when tracking weekly pushing volume) and previously misrouted unknown exercises into `"Back"`.
- **Decision**:
  - Group all working strength sets (`is_warmup == False`) strictly into 4 canonical training categories: **Push**, **Pull**, **Legs**, and **Abs**, each tracked against a **10 sets/week** goal benchmark (`weekly_avg_sets` vs. `10.0`).
  - Route any unrecognized or unassigned exercise to an isolated **`"other"` (`"Other"`)** fallback category, surfaced in the table only when `working_sets > 0`.
  - Retain heaviest working set highlight and deterministic Brzycki estimated 1RM progression per category.
- **Rationale**: Aligns directly with balanced weekly hypertrophy splits (10 working sets/week per movement pattern) and prevents unmapped voice-logged movements from inflating Pull volume.

---

### 3. Telemetry-Less & Strength Workout Drill-Down Rendering

- **Context**: Expanding a strength workout or telemetry-less session previously generated a flat synthetic HR line or displayed an empty 260px chart `<canvas>`, while omitting working sets and workout notes.
- **Decision**:
  - Include `user_notes` and `strength_sets` inside `WorkoutDetailTelemetry`.
  - When `discipline == "strength"` or `time_series` is empty (and no HR/stroke/GPS/split telemetry exists), omit the synthetic fallback series in `AnalyticsService`, hide the chart canvas container completely in `dashboard.html`, and render a structured working-set table (`Exercise`, `Set #`, `Reps`, `Load`, `RPE`, excluding or tagging warmups) alongside summary stats and notes.

---

### 4. Synchronized Dual-Axis Telemetry, Route Map & Multi-Interval Alignment

- **Decision**:
  - **Self-Hosted Chart.js Bundle (`/static/vendor/chart.umd.js`)**: Zero external CDN calls.
  - **Inverted Pace Y-Axis & Proportional Linear X-Axis**: Dual-axis timeline charts use `type: 'linear'` time axes so rest intervals preserve true elapsed width, breaking Pace/SPM traces (`spanGaps: false`) across Concept2 rest periods while tracking recovery HR. Initial Polar GPS-lock slow-speed spikes (`t < 45s`, `> 1.6x` average pace) are filtered, and running tooltips display both `/km` and `/mi`.
  - **Interval Stroke Offset Alignment**: `parse_concept2_strokes()` detects relative timestamp `t` resets between intervals and maps both relative (`set_elapsed_sec`) and cumulative (`elapsed_sec`) coordinates cleanly.
  - **Superimposed Multi-Set Overlay (Pace + HR)**: Plots both normalized Heart Rate and inverted Pace curves (`0:00` to interval duration) across all work intervals, paired with clickable per-interval inline **Workout Graph: Interval N** charts (`Pace`, `SPM`, `Heart Rate`).
  - **Local SVG Run Route Map Card**: Mercator-projected vector SVG (`cos(meanLat)` correction) with Start/Finish pins, elevation ascent/descent, and scale bar, plus `POST /api/v1/workouts/{id}/gpx` for manual GPX attachment without third-party map-tile requests.
  - **Heart Rate Profile Synchronization & Boundary-Safe Classification**:
    - New athlete profiles initialize with a default **Max HR of `185 bpm`** (auto-derived 50/60/70/80/90% zones: Z1 `93–111`, Z2 `111–130`, Z3 `130–148`, Z4 `148–167`, Z5 `167–185`), editable in Settings (`src/static/config.html`) with an "Auto-fill Zones from Max HR" control—never hardcoded into analytics or zone calculation.
    - `PUT /api/v1/profile/heart-rate` persists the athlete's configured thresholds and recalculates Zone 1–5 durations across all historical sessions.
    - `calculate_zone_durations` in `src/services/zone_calculator.py` classifies samples top-down (`bpm >= zone5_min` → `zone4_min` → `zone3_min` → `zone2_min` → `zone1_min`), guaranteeing zero dropped samples on zone boundaries for both contiguous (`148–167`, `167–185`) and inclusive non-overlapping (`148–166`, `167–185`) configurations.

---

## Constitution Compliance Check

| Principle | Requirement | Compliance Strategy | Status |
| :--- | :--- | :--- | :--- |
| **I. Data Sovereignty** | Self-hosted, zero telemetry/location leakage | Self-hosted Chart.js bundle + local SVG GPS route rendering; zero third-party map tiles or CDNs. | ✅ PASS |
| **II. Modular Ingestion** | Adapter isolation & idempotent sync | Ingestion adapters remain decoupled; `Concept2Adapter` and `PolarAdapter` map GPX, zones, and aligned strokes into canonical models cleanly. | ✅ PASS |
| **III. Multimodal Ergonomics** | Mobile-first UX (`375px+`) | Responsive grid cards, scrollable tables, conditional strength set drawers, and touch-friendly date pickers. | ✅ PASS |
| **IV. Unified Volume Modeling** | Zone 2, VO2 Max, strength sets, deterministic 1RM | Dedicated Zone 2 (120m/wk) and VO2 Max (20m/wk) tracking plus Push/Pull/Legs/Abs (10 sets/wk each) with Brzycki 1RM. | ✅ PASS |
| **V. Philosophy-Steered Coaching** | Goal-aligned training volume feedback | Macro weekly targets visually surface aerobic base, anaerobic VO2 stimulus, and balanced resistance volume. | ✅ PASS |
