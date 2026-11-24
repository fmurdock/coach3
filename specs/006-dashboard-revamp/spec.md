# Feature Specification: 006-dashboard-revamp

**Feature Branch**: `feature/006-dashboard-revamp`

**Created**: 2026-11-20

**Updated**: 2026-11-22

**Status**: Ready for Planning

**Input**: Initial dashboard revamp plus athlete feedback updates: separate Zone 2 Cardio card (120 min/week goal), separate VO2 Max Training chart with suggested weekly goal and Zone 4 visibility, resistance volume tracked strictly across Push, Pull, Legs, and Abs (10 sets/week goal each), run GPS route map visualization, clickable per-interval graphs, configurable Max HR defaulting to 185 bpm (never hardcoded) in Settings with auto-recalculation and inclusive zone-boundary classification, and convergence gap fixes (custom date window, notes and strength set lists without blank charts, pace+HR overlay curves, peak interval HR display, and "Other" fallback bucket).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Macro-Level Volume & Weekly Goal Command Center (Priority: P1)

As an athlete, when I land on the dashboard, I want to see dedicated macro-level training volume charts and goal progress for Zone 2 cardio, VO2 max training, and strength training across rolling timeframes so I can immediately verify whether I am hitting my weekly targets.

**Why this priority**: Core value of the macro view; directly answers "Am I hitting 120 minutes/week of Zone 2 aerobic base, meeting my weekly VO2 max target, and completing 10 working sets per week across Push, Pull, Legs, and Abs?"

**Independent Test**: Load the dashboard with synced cardio and resistance workouts across selectable windows (`7d`, `30d`, `90d`, `ytd`, `all`, or custom start/end dates). Verify three distinct top macro widgets render:
1. A dedicated **Zone 2 Cardio** chart displaying accumulated Zone 2 minutes by week against a **120 minutes/week** goal benchmark.
2. A dedicated **VO2 Max Training** chart displaying accumulated Zone 5 (>= 90% max HR) training minutes by week against a suggested **20 minutes/week** goal benchmark.
3. A **Resistance Training Volume** breakdown tracking only **Push, Pull, Legs, and Abs** working set counts against a **10 sets/week** target per category, alongside top working weights and estimated 1RM progression.

**Acceptance Scenarios**:

1. **Given** synced cardio sessions from connected wearables and calibrated user heart rate zones, **When** viewing the top macro section, **Then** display a dedicated Zone 2 Cardio chart showing weekly Zone 2 minutes and cumulative goal progress toward **120 minutes/week**, completely separate from high-intensity training.
2. **Given** synced high-intensity cardio sessions, **When** viewing the VO2 Max Training chart, **Then** display weekly and cumulative Zone 5 ($\ge 90\%$ of configured Max HR) minutes alongside a suggested **20 minutes/week** goal benchmark (~15–20% polarized high-intensity stimulus alongside 120 minutes of Zone 2, equivalent to 1–2 dedicated interval sessions), while also making Zone 4 (80–90% of configured Max HR) minutes visible alongside Zone 5 so hard interval bouts spanning upper Zone 4 and Zone 5 are never hidden.
3. **Given** logged resistance training sessions across arbitrary exercises, **When** viewing the resistance training volume section, **Then** aggregate completed working sets (excluding warmups) exclusively into the 4 categories **Pull, Push, Legs, and Abs**, showing weekly set progress toward **10 sets/week per category**, top working set weight, and estimated 1RM progression.
4. **Given** the timeframe filter controls, **When** the athlete selects preset windows (`7d`, `30d`, `90d`, `ytd`, `all`) or enters a custom start/end date range, **Then** all macro KPIs, Zone 2 / VO2 Max charts, resistance category counts, and personal records refresh to reflect that window.
5. **Given** a new athlete profile or an athlete whose true Max HR differs from defaults, **When** they open Settings, **Then** Max Heart Rate defaults to **185 bpm** (derived into default Zone 1–5 bands, never hardcoded into calculations) and remains freely editable as a Settings input; saving updated Max HR, Resting HR, or Zone 1–5 thresholds automatically recalculates historical workout zone durations without dropping any samples on zone boundaries.

---

### User Story 2 - Recent Workouts Table, Telemetry Drill-Down & Run Route Card (Priority: P1)

As an athlete, when I review my recent training history in the lower dashboard section, I want an interactive table of individual workouts that expands on click to show session summary details, athlete notes, accurate heart rate and pace curves over time, an outdoor GPS route map card, or strength working set logs.

**Why this priority**: Enables rapid inspection of individual workouts—verifying true pacing, cardiovascular response, route geography, and strength logs—without leaving the dashboard.

**Independent Test**: Click an outdoor run row, a rowing/cycling session row, and a strength session row in the recent workouts table. Cardio rows expand to reveal summary metrics, notes, HR zone breakdown, a synchronized dual-axis HR + Pace timeline chart, and (for runs) a self-hosted Route Map card. Strength rows expand to show summary stats, notes, and structured set logs without an empty chart canvas.

**Acceptance Scenarios**:

1. **Given** the recent workouts table, **When** rendered, **Then** display chronological sessions with columns for Date/Time (accurate in local timezone), Sport/Modality, Duration, Primary Volume, Key Highlight Metric, and Inspect action.
2. **Given** a cardio workout row with telemetry, **When** expanded, **Then** render an inline details drawer showing session summary metrics, athlete workout notes, Heart Rate Zone breakdown (`Z1–Z5`), and a synchronized dual-axis timeline chart plotting Heart Rate (bpm) and Pace/Split (inverted, showing both `/km` and `/mi` for runs) over true cumulative elapsed time.
3. **Given** an outdoor run workout, **When** expanded, **Then** render a self-hosted **Run Route Map** card visualizing the GPS track (with Start/Finish markers, distance scale, and elevation gain/loss) using zero external map-tile requests, and allow attaching a GPX route file if historical route coordinates are missing.
4. **Given** a resistance workout or a session without continuous telemetry, **When** expanded, **Then** display summary statistics, athlete notes, and the structured exercise working-set list (exercise name, reps, weight, RPE) **without** rendering a blank or synthetic chart canvas.
5. **Given** an expanded workout row, **When** clicked again or when another workout row is clicked, **Then** collapse the previously expanded drawer cleanly.

---

### User Story 3 - Multi-Set Interval Consistency Analyzer & Per-Interval Graphs (Priority: P2)

As an athlete performing structured interval workouts (such as 4x 4 min on the Concept2 rower with 4 min rest), when I expand an interval workout, I want accurate interval timelines, a superimposed curve overlay comparing both heart rate and pace across sets, a complete interval comparison table, and the ability to expand any single interval row to inspect its own Pace, Stroke Rate, and Heart Rate graph.

**Why this priority**: Essential for evaluating pacing discipline, cardiac drift, and stroke mechanics within and across repeated work intervals.

**Independent Test**: Expand a 4x4 interval rowing session. Verify the Timeline spans the full workout without stacking intervals onto 0:00–4:00, the Multi-Set Curve Overlay superimposes both Pace and Heart Rate curves for Sets 1–4 from 0:00 to 4:00, the interval table displays accurate work and between-set rest rows with Average and Peak/Ending HR, and clicking an interval row opens its inline **Workout Graph: Interval N** chart showing Pace, SPM, and HR.

**Acceptance Scenarios**:

1. **Given** an interval workout where raw stroke timestamps reset at the start of each interval, **When** displayed on the continuous Timeline view, **Then** offset each work interval sequentially by cumulative active and between-set rest elapsed time, breaking Pace/SPM traces cleanly across rest gaps while tracking recovery heart rate.
2. **Given** an interval workout with multiple work bouts, **When** switching to Multi-Set Curve Overlay mode, **Then** superimpose **both heart rate and pace curves** for every work set (`1..N`) aligned from `0:00` to work interval duration alongside a consistency variance badge.
3. **Given** the Split & Interval Breakdown table, **When** rendered, **Then** list sequential work intervals (`Interval 1..N`) and between-set rest periods (excluding non-existent trailing rest after the final interval), displaying Duration, Distance, Average Split/Pace, Average Heart Rate, **Peak/Ending Heart Rate**, Power, and Rest Distance recovery notes.
4. **Given** any work interval or split row with continuous stroke/sample data, **When** the athlete clicks that interval row, **Then** expand an inline single-interval chart (**Workout Graph: Interval N**) displaying inverted **Pace**, **Stroke Rate (SPM)**, and **Heart Rate** over that interval's relative elapsed time (`0:00` to interval length).

---

### Edge Cases

- **Workouts without continuous telemetry (e.g., strength sessions)**: When a workout lacks minute-by-minute heart rate or pace telemetry, the expanded drawer displays summary stats, workout notes, and any logged resistance working sets without rendering an empty or fabricated chart canvas.
- **Unassigned or unrecognized strength exercises**: If a logged strength exercise does not match Push, Pull, Legs, or Abs muscle/movement tags, it maps to a distinct **"Other"** fallback category (surfaced only when non-zero) rather than inflating Pull/Back volume or failing aggregation.
- **Extreme pace variations, flywheel zero-starts, and GPS lock spikes**: Zero-pace flywheel dead-starts (`p = 0`), stopped rest intervals, and early GPS acquisition slowdown spikes are omitted from pace curves rather than stretching the inverted pace scale to infinity/`0:00`.
- **Inclusive vs. contiguous HR zone boundaries**: Whether the athlete configures contiguous zone boundaries (e.g., Zone 4 `148–167`, Zone 5 `167–185`) or non-overlapping inclusive boundaries (e.g., Zone 4 `148–166`, Zone 5 `167–185`), heart rate samples landing exactly on a zone upper boundary (e.g., `166 bpm`) MUST be classified into that zone rather than silently dropped.
- **Mismatched or uncalibrated Max HR**: When an athlete lowers or raises their Max HR input in Settings (defaulting to `185 bpm` for new profiles, never hardcoded in analytics), recalculation updates all historical workouts immediately so Zone 4 and Zone 5 totals accurately reflect their physiological peak.
- **Empty state**: When no workouts exist in the selected timeframe, clear empty-state prompts and a direct link to Settings (integrations and sample data tools) are displayed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a dedicated **Zone 2 Cardio** macro chart/card displaying weekly and cumulative Zone 2 minutes against a **120 minutes/week** target across selectable preset windows (`7d`, `30d`, `90d`, `ytd`, `all`) and custom start/end date ranges.
- **FR-002**: System MUST provide a separate, dedicated **VO2 Max Training** macro chart/card displaying weekly and cumulative Heart Rate Zone 5 ($\ge 90\%$ of configured Max HR) training minutes against a suggested **20 minutes/week** target across the same selectable timeframes, while also surfacing weekly **Zone 4** (80–90% of configured Max HR) minutes alongside Zone 5 so high-intensity interval work spanning upper Zone 4 and Zone 5 is clearly visible and never hidden.
- **FR-003**: System MUST aggregate resistance training volume strictly into the 4 canonical movement/training categories — **Pull, Push, Legs, and Abs** — counting completed working sets (excluding warmups) over the selected window, with an isolated **"Other"** fallback bucket for unmapped exercises.
- **FR-004**: System MUST display resistance training volume in a category breakdown showing weekly/window set counts against a **10 sets/week per category** goal benchmark, top working set weight lifted, and estimated 1RM progression for Pull, Push, Legs, and Abs.
- **FR-005**: System MUST allow athletes to view and edit their **Max Heart Rate** (defaulting to **185 bpm** when creating a new profile, never hardcoded in zone classification), Resting HR, and Zone 1–5 BPM thresholds in Settings—including an auto-derive option from the athlete's configured Max HR—and MUST automatically recalculate historical workout zone durations whenever thresholds are saved.
- **FR-006**: System MUST provide an interactive recent workouts table listing sessions chronologically (in accurate athlete local time) with columns: Date/Time, Sport/Modality badge, Duration, Volume Metric, Key Highlights, and Inspect action.
- **FR-007**: System MUST expand cardio workout rows on click to reveal session summary metrics, athlete notes, Heart Rate Zone breakdown (`Z1–Z5`), and a synchronized dual-axis time-series chart plotting Heart Rate (bpm) and inverted Pace/Split over true cumulative elapsed time.
- **FR-008**: System MUST expand resistance or telemetry-less workout rows on click to display summary metadata, athlete notes, and structured working set logs without rendering an empty or synthetic chart canvas.
- **FR-009**: System MUST render a self-hosted **Run Route Map** card for outdoor runs displaying the GPS track geometry, Start/Finish markers, elevation ascent/descent, and distance scale using strictly local data (zero external map-tile calls), and allow importing a GPX route file for historical runs missing stored coordinates.
- **FR-010**: System MUST provide a **Multi-Set Curve Overlay** mode for multi-interval workouts that superimposes **both Heart Rate and Pace curves** for every work set on a normalized `0:00` to work-duration scale alongside a pacing consistency variance summary.
- **FR-011**: System MUST render a Split & Interval Breakdown table showing sequential work interval numbers (`Interval 1..N`), Duration, Distance, Average Split/Pace, Average Heart Rate, Peak/Ending Heart Rate, Power, between-set rest rows (omitting any trailing rest after the final interval), and rest distance notes.
- **FR-012**: System MUST allow clicking any work interval or split row with continuous samples to expand an inline single-interval chart (**Workout Graph: Interval N**) displaying inverted Pace, Stroke Rate (SPM), and Heart Rate over that interval's elapsed time.
- **FR-013**: System MUST handle multi-interval stroke timestamp resets cleanly during ingestion and analytics so intervals never stack onto `0:00–4:00` and HR zone integration covers full recorded workout duration.
- **FR-014**: System MUST support responsive mobile layouts (down to 375px width for iPhone viewports) and desktop layouts without horizontal page overflow or broken chart scales.
- **FR-015**: System MUST preserve the top navigation shell linking between Gym Mode, Dashboard, AI Coach, and Settings.
- **FR-016**: System MUST classify heart rate samples across Zones 1–5 without dropping boundary BPM values regardless of whether configured zone bounds are contiguous (`zoneX_max == zone(X+1)_min`) or inclusive non-overlapping (`zoneX_max < zone(X+1)_min`).

### Key Entities

- **Zone2CardioSummary**: Aggregated Zone 2 aerobic base duration, weekly breakdown, and progress toward the 120 minutes/week target over the active date window.
- **VO2MaxSummary**: Aggregated Zone 5 (>= 90% max HR) duration, weekly breakdown, and progress toward the suggested 20 minutes/week target over the active date window.
- **StrengthCategoryVolumeSummary**: Working set counts, weekly target progress (10 sets/week), top working set weights, and estimated 1RM progression grouped into **Pull, Push, Legs, and Abs** (plus fallback **Other** when unmapped sets exist).
- **WorkoutDetailView**: Enriched session record containing summary statistics, athlete notes, HR zone durations, strength set breakdown (for resistance workouts), continuous telemetry time series (elapsed time, heart rate, pace, watts, stroke rate), structured intervals/splits (including average, ending, and peak HR), and GPS route coordinates.
- **IntervalOverlayDataset**: Time-normalized telemetry slices (interval elapsed time, heart rate, pace, cadence/SPM) for each work interval supporting both superimposed multi-set comparison and individual inline interval charts.
- **RunRouteTrack**: Chronological GPS coordinate points (latitude, longitude, elevation, elapsed seconds) enabling local route map rendering and elevation gain/loss calculation.
- **HeartRateZoneProfile**: Athlete-configured Resting HR, Max HR, and Zone 1–5 lower/upper BPM thresholds governing zone classification across all workouts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Athlete can view separate Zone 2 Cardio progress (vs. 120 min/week goal), VO2 Max progress (vs. 20 min/week goal), and Push/Pull/Legs/Abs working set progress (vs. 10 sets/week goal each) within 500ms of page load.
- **SC-002**: Clicking any workout row expands its details drawer (telemetry chart, route card, notes, and/or resistance set table) in under 200ms without page reloads.
- **SC-003**: Athletes can compare pacing and heart rate consistency across all sets of a structured interval workout in under 5 seconds via superimposed Pace + HR overlays and clickable single-interval Pace/SPM/HR graphs.
- **SC-004**: Heart rate zone totals and interval splits match connected Polar and Concept2 source records cleanly (no stacked timestamps, timezone shifts, or missing telemetry streams).
- **SC-005**: Dashboard and inline charts remain readable on 375px-wide mobile viewports with zero horizontal page overflow.
- **SC-006**: All telemetry visualization, including the Run Route Map card and charts, executes strictly locally with zero external tracking or third-party tile/CDN transmission of athlete location or biometrics.

## Assumptions

- **Weekly VO2 Max Target Rationale**: Alongside a 120 minutes/week Zone 2 aerobic base target, a **20 minutes/week** Zone 5 ($\ge 90\%$ of configured Max HR) goal follows an ~80/20 to 85/15 polarized distribution (representing roughly 1–2 dedicated high-intensity interval workouts per week, such as a 4x4-minute interval session). Weekly targets (`120 min` Zone 2, `20 min` VO2 Max, `10 sets` per strength category) serve as built-in dashboard defaults.
- **Default Heart Rate Profile**: New athlete profiles initialize with a default **Max HR of 185 bpm** (with standard 50/60/70/80/90% zone boundaries: Z1 `93–111`, Z2 `111–130`, Z3 `130–148`, Z4 `148–167`, Z5 `167–185`), but all zone calculations dynamically read the athlete's stored Settings profile rather than hardcoding `185`.
- **Weekly Resistance Goal Scaling**: For multi-week windows (`30d`, `90d`), weekly goal progress for Zone 2 (120 min/wk), VO2 Max (20 min/wk), and Push/Pull/Legs/Abs (10 sets/wk each) normalizes to average weekly volume (`total / weeks_in_window`) against the weekly target.
- **Push / Pull / Legs / Abs Exercise Mapping**: Existing exercise muscle metadata maps deterministically to the 4 training categories:
  - **Push**: chest, pectorals, shoulders, deltoids, triceps, dips, presses.
  - **Pull**: back, lats, traps, rhomboids, biceps, forearms, rows, pull-ups, curls.
  - **Legs**: quadriceps, hamstrings, glutes, calves, squats, deadlifts, lunges, hinges.
  - **Abs**: abs, core, abdominals, obliques, planks, leg raises.
- Concept2 and Polar APIs provide periodic/stroke telemetry when recorded; historical workouts synced prior to route/stroke ingestion can attach GPX exports or be re-synced cleanly.
