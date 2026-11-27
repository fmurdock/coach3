# Feature Specification: Gym Session Hygiene, Dashboard Cardio/Lifting Tabs, Professional UI Polish, and LLM Connection Verification

**Feature Branch**: `008-remediation2`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Lazy gym session creation so we don't have blank 0-set workouts; Separate the dashboard into tabs for cardio and lifting; Change the design so it looks less flashy and more user friendly and professional; Fix the LLM server connections. Add a test that sends a short relevant prompt and expects an output."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Zero-Blank-Workout Gym Logging (Priority: P1)

As an athlete opening Gym Mode on my phone or desktop, I want visiting the Gym Mode screen without logging any sets to leave my workout history completely clean, and I want a strength workout session to be created only when I actually confirm and save my first set (and removed if I delete the last remaining set).

**Why this priority**: Currently, merely opening Gym Mode creates a blank 0-set workout record in the athlete's history, polluting the Dashboard and exports with phantom workouts.

**Independent Test**: Open Gym Mode without submitting any sets and verify no new workout appears in history; then submit a set and verify a single strength session is created with the athlete's local date; finally delete that only set and verify the empty session is removed.

**Acceptance Scenarios**:

1. **Given** no active strength session exists in the current 4-hour window, **When** an athlete opens Gym Mode and navigates away without logging any sets, **Then** zero new workout sessions are created and the Dashboard workout history remains unchanged.
2. **Given** no active strength session exists, **When** the athlete stages and confirms their first set (online or synced from the offline queue), **Then** a strength session is created automatically using the athlete's local calendar date in its title, the set is attached to it, and subsequent sets within the 4-hour window attach to that same session.
3. **Given** an active strength session with only one logged set, **When** the athlete deletes that set, **Then** the empty strength session is automatically removed so no 0-set workout remains in history.

---

### User Story 2 - Reliable AI Server Connections & Live Prompt Verification (Priority: P1)

As an athlete configuring an AI coaching provider (cloud or local inference server), I want connection setup, connection testing, and inference requests to connect reliably and surface clear, accurate diagnostics—and I want an automated verification test that sends a short, fitness-relevant prompt to confirm a real output is returned.

**Why this priority**: Broken AI server connections block both AI workout critiques and forward training plan generation, and an automated prompt-and-output test prevents silent regressions.

**Independent Test**: Configure an AI provider, run the connection test, and execute the automated verification test that sends a short fitness-relevant prompt and asserts a non-empty, valid output.

**Acceptance Scenarios**:

1. **Given** a configured cloud or local AI provider with valid settings, **When** the athlete tests the connection or runs coaching analysis/planning, **Then** the system connects successfully without transport, URL, header, or payload formatting errors.
2. **Given** an unreachable local AI server, mismatched endpoint path, or invalid credentials, **When** the athlete tests the connection, **Then** the system reports a clear, actionable status message explaining why the connection failed.
3. **Given** the automated verification suite, **When** the AI connection verification test runs, **Then** it sends a short, fitness-relevant prompt and asserts that a non-empty output is returned.

---

### User Story 3 - Dedicated Cardio and Lifting Dashboard Tabs (Priority: P2)

As an athlete reviewing my training on the Dashboard, I want the Dashboard separated into distinct **Cardio** and **Lifting** tabs so I can inspect endurance metrics and cardio sessions separately from strength volume, estimated 1RMs, personal records, and lifting sessions without visual clutter.

**Why this priority**: Combining endurance zones/pace charts and strength muscle-group/1RM tables on a single long scrolling view makes it harder to focus on either modality.

**Independent Test**: Open the Dashboard, switch between the Cardio and Lifting tabs across different time windows, and verify each tab displays only its relevant metrics, charts, and workout history.

**Acceptance Scenarios**:

1. **Given** an athlete with both cardio (runs, rows, erg bike) and lifting workouts, **When** they open the Dashboard, **Then** they see clear **Cardio** and **Lifting** tabs, with one tab active by default and the other hidden until selected.
2. **Given** the **Cardio** tab is active, **When** the athlete views the Dashboard, **Then** they see endurance-specific summaries (Zone 2 volume, VO2 Max volume, weekly cardio trends) and cardio workout history.
3. **Given** the **Lifting** tab is active, **When** the athlete views the Dashboard, **Then** they see strength-specific summaries (Push/Pull/Legs/Abs volume, top lifts, estimated 1RM, personal records) and lifting workout history.
4. **Given** the athlete changes the selected time window (e.g., 7d, 30d, 90d, custom) while on either tab, **When** they switch tabs, **Then** both tabs reflect the active time window consistently.

---

### User Story 4 - Calm, User-Friendly, and Professional Visual Design (Priority: P2)

As an athlete using Coach3 daily across desktop and mobile, I want a clean, restrained, user-friendly, and professional visual design—without overly flashy neon gradients, heavy glow effects, or distracting visual noise—so data, charts, and controls are effortless to read and operate.

**Why this priority**: Reducing visual flashiness improves legibility, trust, and everyday usability for a personal training logbook and analytics tool.

**Independent Test**: Inspect all primary web views (Dashboard, Gym Mode, AI Coach, Settings, Sign In) on desktop and mobile viewports to confirm a cohesive, restrained, high-contrast, professional design with clear hierarchy and accessible controls.

**Acceptance Scenarios**:

1. **Given** any primary web page (Dashboard, Gym Mode, AI Coach, Settings, Sign In), **When** viewed on desktop or mobile, **Then** the layout uses a calm, cohesive color palette, subtle borders/surfaces instead of heavy glows or flashy gradients, clear typographic hierarchy, and comfortable spacing.
2. **Given** interactive controls (tabs, buttons, forms, charts, status badges), **When** hovered, focused, or tapped, **Then** they provide clear, accessible feedback without jarring animations or visual clutter.

---

### Edge Cases

- **Refreshing Gym Mode before logging a set**: Reloading Gym Mode when no sets have been logged yet must still leave zero workout rows in history.
- **Offline queue flush on a fresh Gym Mode visit**: If sets were queued offline before any session existed in the database, flushing the queue when connectivity returns must lazily create the session and attach all queued sets without failing.
- **Switching Dashboard tabs with an open workout detail view**: Switching between Cardio and Lifting tabs must not leave stale or mismatched workout detail panels visible from the other modality.
- **Zero cardio or zero lifting workouts in a selected window**: Switching to a tab with no workouts in the selected period must display a clean, helpful empty state rather than broken charts or blank space.
- **Local AI server URL variations**: Users entering a local AI server base URL with or without a trailing slash or path suffix must either connect cleanly or receive a clear normalization/validation message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Opening Gym Mode MUST NOT create or persist a workout session record until at least one strength set is actually committed.
- **FR-002**: Committing strength sets without a pre-existing session MUST lazily attach to an active strength session within the recent 4-hour window if one exists, or create a new strength session titled with the athlete's configured local calendar date.
- **FR-003**: Deleting the last remaining strength set of a gym-logged strength session MUST automatically remove the now-empty workout session record.
- **FR-004**: Offline-queued strength set submissions MUST be able to sync cleanly upon reconnect even when no session existed at the time the sets were queued.
- **FR-005**: The Dashboard MUST organize its analytics, charts, personal records, and workout history into separate **Cardio** and **Lifting** tabs.
- **FR-006**: Switching between **Cardio** and **Lifting** tabs MUST preserve the athlete's selected time-window filter and display clean empty states when a modality has no workouts in that window.
- **FR-007**: The application's visual design across all web pages MUST use a restrained, user-friendly, professional aesthetic—replacing flashy gradients, heavy glow effects, and noisy accents with clean surfaces, clear typography, accessible contrast, and consistent spacing.
- **FR-008**: AI provider connections (both cloud and self-hosted local inference servers) MUST connect reliably for health checks and structured generation, handling URL formatting, headers, and error reporting cleanly.
- **FR-009**: The automated test suite MUST include a test that sends a short, fitness-relevant prompt through the AI connection layer and verifies that a non-empty output is returned.

### Key Entities

- **Active Gym Session**: A strength workout session that exists in persistent storage only once at least one strength set has been committed to it, scoped to the athlete's local date.
- **Dashboard Modality View**: A tab-separated presentation of training data partitioned into **Cardio** (endurance activities and heart-rate zone metrics) and **Lifting** (resistance sets, muscle-group volume, and strength PRs).
- **AI Provider Connection**: The configured cloud or local inference endpoint and credentials used for live connectivity checks and fitness coaching prompt execution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Opening Gym Mode and leaving without logging sets creates 0 workout records; logging sets and then deleting all of them also leaves 0 empty workout records.
- **SC-002**: 100% of cardio metrics/sessions appear under the Dashboard **Cardio** tab and 100% of lifting metrics/PRs/sessions appear under the **Lifting** tab, with instant tab switching and consistent time-window filtering.
- **SC-003**: All primary web pages pass visual review for a clean, calm, professional layout with zero overlapping elements, readable contrast, and full mobile usability.
- **SC-004**: AI server connection checks succeed against valid cloud and local server configurations, and the automated prompt-and-output test passes reliably by sending a short fitness-relevant prompt and verifying a non-empty response.

## Assumptions

- Existing single-athlete authentication, data sovereignty, and privacy-scrubbing protections from `007-remediation` remain enforced.
- Existing empty `0`-set gym sessions created prior to this change in local development databases can be cleaned up without affecting any authentic logged workouts.
- The automated prompt-and-output test will support deterministic mocked/contract execution in standard CI/offline test runs and can also target a live configured AI server when available.
