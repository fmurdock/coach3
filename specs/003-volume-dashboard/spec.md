# Feature Specification: Unified Training Volume Modeling and Peak Performance Dashboard

**Feature Branch**: `feature/003-volume-dashboard`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Unified training volume modeling and peak performance dashboard: Historical volume analytics aggregating running weekly mileage, Zone 2 cardio duration, Concept2 meters/split distributions, and strength effective sets & volume load (sets x reps x weight, plus bodyweight added load); historical personal record (PR) and peak performance tracking across rolling time windows (e.g. 1RM/5RM estimates, 5k/10k best pace, 500m/2k erg peaks); interactive visual web dashboard with charts and date-range filters."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Historical Cardiovascular Volume & Zone 2 Analytics (Priority: P1)

An endurance athlete accesses their self-hosted dashboard to review training volume over rolling time windows (e.g. last 7 days, 30 days, 90 days, or custom date range). The dashboard displays total running mileage, Zone 2 duration, cardiovascular time distribution across Zones 1–5, and Concept2 erg meters with average 500m split times.

**Why this priority**: Monitoring aerobic base volume and Zone 2 polarized distribution is essential for endurance progression and preventing overtraining.

**Independent Test**: Can be tested independently by querying analytics endpoints with date-range parameters over populated workout sessions, verifying that total distance, Zone 2 minutes, and split distributions match exact database aggregates.

**Acceptance Scenarios**:
1. **Given** an athlete with outdoor running sessions in the past 30 days, **When** they view the 30-day dashboard, **Then** the system displays total mileage, average pace, and total Zone 2 duration (in hours and minutes) alongside a weekly trend chart.
2. **Given** Concept2 erg row and erg bike workouts, **When** analytics are queried, **Then** total meters rowed/biked, total duration, and average 500m pace are presented with discipline breakdown.
3. **Given** a user switching between preset time windows (7D, 30D, 90D, YTD, All), **When** clicked, **Then** all cardio metrics update instantly without page reloads.

---

### User Story 2 - Strength Volume Load & Muscle Group Distribution (Priority: P1)

A strength athlete reviews resistance training volume across muscle groups and workout sessions. The system calculates effective working sets (excluding warmup sets), total volume load ($\text{sets} \times \text{reps} \times \text{weight}$), and aggregates external added resistance for calisthenic movements (e.g., weighted pull-ups and dips).

**Why this priority**: Tracking total volume load and set count per muscle group is the fundamental driver of hypertrophy and progressive overload.

**Independent Test**: Can be tested by computing volume load and effective sets for logged `strength_sets`, verifying that warmup sets are omitted from effective set tallies, bodyweight added loads are cleanly integrated, and volume load by muscle group matches mathematical expectations.

**Acceptance Scenarios**:
1. **Given** logged strength sets for Barbell Back Squat and Pull-Up, **When** strength analytics are loaded, **Then** the system reports effective sets and total tonnage/volume load grouped by exercise and primary muscle group (e.g. quadriceps, back).
2. **Given** weighted calisthenic sets (e.g. 3 sets of 12 pull-ups with +30 lbs), **When** volume load is computed, **Then** the system transparently reports external added load volume ($3 \times 12 \times 30\text{ lbs} = 1,080\text{ lbs}$) alongside repetition counts.
3. **Given** sets flagged as warmup (`is_warmup = true`), **When** effective sets are calculated, **Then** warmup sets are excluded from weekly muscle group set targets.

---

### User Story 3 - Historical Personal Records (PR) & Peak Performance Tracking (Priority: P2)

An athlete views their historical best performances and personal records across rolling time windows. For strength, the system displays all-time and recent estimated 1-Rep Max (1RM) and 5-Rep Max (5RM) per exercise. For cardio, the system displays best pace across benchmark distances (1 mile, 5k, 10k) and best Concept2 erg times (500m, 2,000m, 5,000m), highlighting newly minted PRs.

**Why this priority**: Tracking personal records provides concrete feedback on training effectiveness and validates progressive overload across training cycles.

**Independent Test**: Can be tested by submitting workouts with incremental peak performances and verifying that deterministic PR detection correctly identifies all-time and rolling window bests.

**Acceptance Scenarios**:
1. **Given** a set of 5 reps at 225 lbs on bench press, **When** PR analytics are computed, **Then** the system calculates an estimated 1RM (e.g., ~262 lbs) and checks whether this represents an all-time or window PR.
2. **Given** running sessions of varying distances, **When** endurance PRs are evaluated, **Then** the system identifies the athlete's fastest 5k and 10k paces.
3. **Given** Concept2 erg sessions, **When** erg PRs are evaluated, **Then** the system reports peak power, best 500m split, and fastest 2k time.

---

### User Story 4 - Interactive Visual Web Dashboard with Responsive Charts (Priority: P2)

An athlete opens the Coach3 dashboard on desktop or mobile iPhone. The dashboard renders high-contrast, interactive visual charts: weekly cardio mileage bars, Zone 2 duration distribution, strength volume load line curves, muscle group distribution radar/bars, and a recent PR achievement feed.

**Why this priority**: Visual feedback transforms raw tabular data into intuitive training insights, enabling quick adjustments before the next workout.

**Independent Test**: Can be tested by loading `/dashboard` in a browser, verifying that all charts render cleanly with zero external CDN dependencies, and testing filter toggles.

**Acceptance Scenarios**:
1. **Given** an athlete loading `/dashboard`, **When** rendered, **Then** they see cohesive cards for Cardio Volume, Strength Volume, Heart Rate Zone Distribution, and PR Showcase.
2. **Given** date filter buttons (7D, 30D, 90D, YTD, All), **When** tapped, **Then** charts re-animate smoothly with updated datasets.

---

### Edge Cases

- **Zero Cardio or Zero Strength Sessions in Window**: Athlete has only run or only lifted in the selected window. The system gracefully renders zero-state cards for the empty discipline without breaking the active discipline's charts.
- **Bodyweight-Only Movements in 1RM Calculations**: For pure bodyweight exercises (pushups, bodyweight pullups) with zero added weight, traditional 1RM weight math is non-applicable. System tracks repetition PRs (e.g. max reps in a single set) rather than artificially calculating 0 lb 1RM.
- **Extreme Rep Counts (>15 reps) in 1RM Estimation**: 1RM formulas (Epley/Brzycki) degrade in accuracy above 10–12 reps. System caps 1RM estimation to sets of 10 or fewer reps, or flags sets $>10$ reps as endurance sets.
- **Split Units**: Athlete switches between pounds and kilograms across sessions. System normalizes all volume load calculations into the athlete's preferred profile unit (default: lbs) before aggregating.
- **Sub-Distance Runs**: A run of 4.8 km should not be mistakenly evaluated as an incomplete 5k PR unless explicit rolling distance segmentation is enabled.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST calculate aggregate cardiovascular volume metrics across user-selectable date windows (start date, end date): total distance, active duration, total calories, and discipline-specific totals (outdoor run, erg row, erg bike).
- **FR-002**: System MUST aggregate time spent in Heart Rate Zones 1 through 5, highlighting total Zone 2 duration in hours, minutes, and percentage of total training time.
- **FR-003**: System MUST calculate strength training volume metrics: total volume load ($\sum \text{sets} \times \text{reps} \times \text{weight}$), total repetitions, and count of effective working sets (excluding warmup sets).
- **FR-004**: System MUST aggregate strength volume by primary muscle group (chest, back, quadriceps, hamstrings, shoulders, arms, core, glutes, calves, full body).
- **FR-005**: System MUST calculate estimated 1-Rep Max (1RM) and 5-Rep Max (5RM) for strength exercises using the standard Epley formula ($\text{weight} \times (1 + \text{reps} / 30)$) capped at sets of 10 or fewer completed repetitions; sets exceeding 10 reps MUST be classified as muscular endurance sets and excluded from maximum strength 1RM estimation.
- **FR-006**: System MUST track historical Personal Records (PRs) for each exercise: all-time heaviest load, all-time highest estimated 1RM, and peak performance within the active filter window.
- **FR-007**: System MUST track endurance PRs across standard milestones (1 mile, 5k, 10k, 500m erg, 2,000m erg, 5,000m erg) by matching completed workout sessions within a $\pm 3\%$ distance tolerance and ranking the fastest recorded pace and total elapsed time.
- **FR-008**: System MUST serve an interactive, mobile-optimized visual dashboard at `/dashboard` rendering volume trends, heart rate distributions, and PR achievements using a self-hosted standalone Chart.js bundle stored locally in `src/static/` with zero external CDN dependencies.
- **FR-009**: System MUST provide date-range filtering presets: "Last 7 Days", "Last 30 Days", "Last 90 Days", "Year to Date", and "All Time", plus custom start/end date bounds.
- **FR-010**: System MUST expose REST API analytics endpoints: `GET /api/v1/analytics/summary`, `GET /api/v1/analytics/cardio`, `GET /api/v1/analytics/strength`, and `GET /api/v1/analytics/prs`.
- **FR-011**: System MUST normalize all weight volume aggregates into the user's preferred unit (`lbs` or `kg`) using standard conversion ($1\text{ kg} = 2.20462\text{ lbs}$).
- **FR-012**: System MUST isolate and report external added load on bodyweight movements as a distinct volume component without distorting pure barbell volume.

### Key Entities *(include if feature involves data)*

- **VolumeSummary**: Unified aggregate container for a given time window (start date, end date, total training duration, cardio distance, strength volume load, effective set count, Zone 2 duration).
- **CardioVolumeMetrics**: Detailed cardio breakdown (running mileage, erg meters, pace distributions, Zone 1–5 duration and percentages).
- **StrengthVolumeMetrics**: Detailed resistance training breakdown (effective sets by muscle group, total tonnage, volume load by exercise, total reps, added bodyweight load).
- **PersonalRecord**: Historical best performance record (exercise/discipline, milestone/metric type, record value, date achieved, workout session ID, previous record value).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard analytics endpoints return complete 90-day volume and PR aggregates in under 120ms on self-hosted hardware.
- **SC-002**: 100% of warmup sets are correctly filtered out from effective working set volume tallies.
- **SC-003**: 100% of bodyweight movements with added resistance reflect exact external load without overwriting total load.
- **SC-004**: Personal record detection is 100% deterministic and reproducible across repeated historical recalculations.
- **SC-005**: The visual dashboard operates completely offline-capable and self-hosted with zero external CDN dependencies or data leaks.

---

## Assumptions

- **Single Athlete Focus**: Calculations and dashboard queries operate on the default authenticated user's training history.
- **Data Availability**: The database contains sessions ingested from Feature 1 (running, row/bike erg) and/or Feature 2 (strength sets).
- **Rep Cap on 1RM**: Sets exceeding 10–12 repetitions are treated as muscular endurance sets and not used to estimate maximum single-rep strength.
- **Browser Compatibility**: The dashboard runs on modern evergreen desktop and mobile browsers (iOS Safari, Chrome, Firefox).
