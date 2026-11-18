# Feature Specification: Core Data Ingestion & Telemetry Models

**Feature Branch**: `001-data-ingestion`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Core self-hosted database models and ingestion connectors for Polar AccessLink (outdoor running) and Concept2 Logbook API (erg bike and rower)."

## Clarifications

### Session 2026-11-17
- Q: How should heart rate zone distribution (such as minutes in Zone 2) be determined across both Polar and Concept2 workouts? → A: Option A (Unified local calculation: Coach3 stores the user's HR profile and calculates Zones 1–5 durations from raw HR samples across all activities).
- Q: When you first connect your Polar or Concept2 accounts, how much historical workout history should Coach3 import? → A: Option A (All-time history: Automatically backfill all available historical workouts from account inception in the background with pagination and rate-limit backoff).
- Q: For outdoor running sessions synced from Polar, should Coach3 store the full second-by-second GPS coordinate stream, or only route summary and map polyline data? → A: Option A (Full route & GPS points: Store granular timestamped latitude, longitude, and elevation points for high-resolution route rendering and analysis).
- Q: If a workout is modified or deleted on Polar Flow or Concept2 Logbook after Coach3 has already imported it, how should Coach3 reconcile the change? → A: Option A (Soft-sync & archive: Update modified metrics and telemetry; if deleted upstream, preserve local data and mark as "Archived / Removed Upstream" to prevent accidental data loss).
- Q: What default background polling schedule should Coach3 use to check for newly completed workouts from Polar and Concept2? → A: Option B (Fixed hourly polling: Poll once every 60 minutes 24/7, plus an instant "Sync Now" manual trigger).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Polar Outdoor Running Ingestion (Priority: P1)

As an endurance athlete, I want to connect my Polar account so that my outdoor running sessions and detailed cardiovascular metrics automatically sync into my self-hosted workout database without manual data entry.

**Why this priority**: Outdoor running is the primary cardio modality. Capturing accurate distance, duration, pace, and heart rate telemetry forms the foundation of all volume and Zone 2 analysis.

**Independent Test**: Can be tested by providing a Polar AccessLink OAuth token and fetching a sample run; verifies that distance, pace, duration, and heart rate zones are accurately stored in the local database.

**Acceptance Scenarios**:

1. **Given** a linked Polar account with new outdoor running workouts, **When** synchronization is triggered, **Then** all new running sessions are imported with total distance, active duration, average pace, elevation profile, and heart rate zone distribution.
2. **Given** an already-imported Polar workout, **When** synchronization runs again, **Then** the system detects the existing external workout identifier, updates any modified fields if necessary, and produces zero duplicate entries.
3. **Given** a run recorded without heart rate data (e.g., GPS watch only), **When** imported, **Then** the workout is successfully saved with pace and distance intact, cleanly marking heart rate metrics as absent.

---

### User Story 2 - Concept2 Erg Bike & Rower Ingestion (Priority: P2)

As a hybrid athlete, I want to connect my Concept2 Logbook so that my indoor rowing and erg bike workouts sync seamlessly into the same unified workout store.

**Why this priority**: Rowing and erg biking represent the user's primary indoor and non-impact cardiovascular training. Consolidating them alongside running is critical for holistic training volume.

**Independent Test**: Can be tested independently by authenticating with Concept2 Logbook credentials, fetching a row and a bike workout, and verifying that stroke rate, split time, and wattage are preserved and mapped to the appropriate equipment type.

**Acceptance Scenarios**:

1. **Given** a linked Concept2 Logbook account with rower and bike erg activities, **When** synchronization is initiated, **Then** both workout types are imported, properly categorized by equipment type (rower vs. bike erg), with split times (per 500m/1000m), power (watts), cadence (strokes per minute / RPM), and total distance.
2. **Given** a Concept2 interval workout (e.g., 5 x 500m with rest intervals), **When** ingested, **Then** the system records both the overall session summary and the individual interval splits.

---

### User Story 3 - Unified Workout Inspection & Ingestion Audit Log (Priority: P3)

As a self-hosted user, I want to view a log of recent sync operations and inspect normalized workout entries so that I have complete transparency into my data pipeline and can verify data integrity.

**Why this priority**: In self-hosted architectures, data ownership requires visibility. Users need to verify that third-party syncs are healthy, see when data was last refreshed, and inspect raw-to-canonical mappings.

**Independent Test**: Can be tested by querying the sync log endpoint/view to inspect timestamps, records imported, errors encountered, and normalized workout summaries.

**Acceptance Scenarios**:

1. **Given** a completed sync run, **When** the user checks sync history, **Then** the system displays the timestamp, source provider (Polar or Concept2), number of items processed, and status (success, partial, failed).
2. **Given** an invalid or expired API token for an external service, **When** synchronization is attempted, **Then** the system records a clear authentication error in the sync log without crashing or corrupting existing records.

---

### Edge Cases

- **Network Timeouts & Rate Limits**: If external API requests to Polar or Concept2 fail due to network drops or HTTP 429 rate limits, the ingestion adapter must pause, log the failure, and resume from the last successful cursor on the next attempt.
- **Clock Skew & Timezone Shifts**: When workouts are recorded across timezones, start timestamps must be normalized to UTC for storage while preserving the athlete's local workout time for user-facing displays.
- **Partial Telemetry**: Workouts missing specific sensors (e.g., no heart rate monitor, or erg without stroke power) must still save gracefully without breaking downstream aggregations.
- **Duplicate Sync Invocations**: Simultaneous or overlapping sync triggers must be deduplicated via database locks or transactional idempotency checks.
- **Retroactive Edits & Deletions**: If an athlete edits a workout title, distance, or notes on Polar Flow or Concept2 Logbook, subsequent syncs update existing telemetry while preserving local user annotations. If a workout is deleted upstream, Coach3 marks the local session as archived rather than permanently deleting historical data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an ingestion adapter for Polar AccessLink capable of authenticating and synchronizing outdoor running sessions.
- **FR-002**: System MUST extract Polar running metrics: start timestamp, total duration, active duration, total distance, average pace, elevation gain/loss, average heart rate, maximum heart rate, granular time-series heart rate samples, and timestamped GPS coordinates (latitude, longitude, altitude) for outdoor runs.
- **FR-003**: System MUST provide an ingestion adapter for Concept2 Logbook capable of authenticating and synchronizing indoor rower and erg bike sessions, extracting time-series heart rate samples when recorded.
- **FR-004**: System MUST extract and normalize Concept2 workout metrics: discipline type (rower or bike erg), start timestamp, elapsed duration, total distance, average and interval split times, average power (watts), average stroke rate (strokes per minute / cadence), and drag factor.
- **FR-005**: System MUST normalize disparate data formats from Polar and Concept2 into a single canonical endurance workout entity.
- **FR-006**: System MUST compute cardiovascular zone allocations (time in Zone 1 through Zone 5) locally from raw heart rate samples using a single, unified user heart rate profile across all activities (Polar runs, Concept2 rows, Concept2 bike ergs).
- **FR-007**: System MUST enforce idempotency on all ingestion pipelines using the external provider's unique workout identifier; re-importing an existing workout MUST NOT duplicate sessions or distort volume metrics.
- **FR-008**: System MUST securely persist external authentication credentials and tokens locally in accordance with self-hosted data sovereignty rules, never exposing them to external third parties.
- **FR-009**: System MUST maintain an audit log of all synchronization attempts, recording the source, start time, completion time, items created, items updated, and error messages if applicable.
- **FR-010**: System MUST execute background synchronization on a fixed 60-minute recurring schedule 24/7, while also providing an instant on-demand manual sync trigger.
- **FR-011**: System MUST preserve interval-level split data for structured workouts where provided by the source API.
- **FR-012**: System MUST automatically backfill full account history upon initial connection, using paginated background jobs with rate-limit backoff and checkpointed sync cursors to resume reliably after interruptions.
- **FR-013**: System MUST apply a soft-sync reconciliation strategy for upstream modifications and deletions: incoming edits MUST update telemetry and metrics without overwriting local user notes or tags; if a workout is removed upstream, the local record MUST be marked as "Archived (Removed Upstream)" rather than permanently deleted.

### Key Entities *(include if feature involves data)*

- **Workout Session**: Represents a single completed athletic activity. Key attributes include local identifier, external source identifier, provider name (Polar, Concept2), activity discipline (run, row, bike erg), start time (UTC), local start time, total elapsed duration, active duration, total distance, energy expenditure (calories), and sync status.
- **Heart Rate Stream / Zones**: Cardiovascular telemetry associated with a workout session. Includes raw time-series heart rate samples and Coach3-computed durations in Zone 1 through Zone 5.
- **GPS Route Stream**: Time-series geographic coordinates (latitude, longitude, altitude, timestamp) associated with outdoor runs, enabling interactive map rendering and elevation profiles.
- **User Heart Rate Profile**: User biometrics defining resting heart rate, maximum heart rate, and custom or formula-based threshold boundaries for Zone 1 through Zone 5.
- **Split / Interval**: Sub-session performance segments (e.g., kilometer splits for runs, 500m/interval splits for rowing). Includes split index, split distance, elapsed split time, average split pace, and average power.
- **Integration Account**: Configuration state for an external provider. Stores provider type, account identifier, encrypted access/refresh credentials, last successful sync timestamp, and polling status.
- **Sync Audit Log**: Operational log entry documenting an individual sync job execution, status (success, partial, failed), processed item counts, and diagnostic messages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of standard running workouts from Polar and erg workouts from Concept2 imported during testing map to the canonical workout model without missing core metrics (duration, distance, equipment/discipline).
- **SC-002**: Running 5 consecutive sync operations with identical external data produces zero duplicate workouts and zero variance in cumulative volume.
- **SC-003**: Ingestion of a standard 60-minute workout containing split intervals and heart rate telemetry completes in under 2 seconds from API receipt to local database persistence.
- **SC-004**: System recovers gracefully from 100% of simulated network dropouts or invalid credentials, recording an audit log entry with zero database corruption.
- **SC-005**: Users can view the complete list of synced workouts and their detailed metrics immediately upon sync completion.

## Assumptions

- **Credential Acquisition**: The user has obtained or can input the necessary developer/client credentials (e.g., Client ID and Secret) for Polar AccessLink and Concept2 Logbook API.
- **Sync Architecture**: Because the backend is self-hosted (potentially behind local home routers or NATs without public ingress), ingestion relies primarily on scheduled polling and on-demand manual triggers rather than external incoming webhooks.
- **Data Retention**: All ingested historical workouts and telemetry samples are retained indefinitely on the local system unless explicitly deleted by the user.
- **Unit Conventions**: Metrics are normalized and stored in standard scientific units internally (meters, seconds, watts, beats per minute) while allowing presentation layers to format into imperial or metric user preferences (e.g., miles, /500m pace, min/mile).
