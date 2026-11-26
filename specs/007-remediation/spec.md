# Feature Specification: Comprehensive Security, Data Integrity, Reliability, and Quality Remediation

**Feature Branch**: `007-remediation`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Remediate all P0, P1, and P2 findings from the full Coach3 codebase audit covering startup/deployment reliability, security & data sovereignty, lossless third-party workout synchronization, accurate telemetry & analytics math, resilient gym voice logging, performance at scale, everyday usability & data export, and long-term maintainability."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hardened Deployment, Access Security, and Data Sovereignty (Priority: P1)

As a self-hosted athlete running Coach3 on personal hardware or a home network, I want the application to start reliably out of the box, protect my biometric data and third-party credentials from unauthorized access or leakage, scrub personal identifiers before any cloud AI call, and safely render all text in the browser.

**Why this priority**: These are critical security, privacy, and startup defects (P0 audit items). Until resolved, the containerized deployment cannot boot cleanly, sensitive health/GPS records and third-party API keys are exposed to unauthorized access or leakage, and untrusted text can execute scripts in the browser.

**Independent Test**: Deploy the application cleanly into an empty environment, verify startup health and automatic schema initialization, attempt unauthorized and cross-origin access, complete an OAuth callback with tampered state, submit an AI request with PII in notes and goals, and render HTML/script payloads inside workout notes, titles, and AI responses.

**Acceptance Scenarios**:

1. **Given** a fresh deployment with a valid encryption key and an empty database, **When** the application starts, **Then** it initializes required data structures automatically, runs under a non-privileged account, and reports healthy only when its database is reachable.
2. **Given** a deployment started without an explicit encryption key (outside automated tests), **When** startup runs, **Then** the system refuses to boot with a clear configuration error rather than falling back to a hardcoded default key.
3. **Given** an unauthenticated visitor or an untrusted external website, **When** they attempt to read workout history, modify integration credentials, trigger AI analysis, or reset demo data, **Then** the request is rejected and cross-origin access is denied.
4. **Given** an OAuth authorization callback with a missing, expired, or mismatched state value, **When** the callback is received, **Then** the system rejects the authorization and does not link or overwrite any athlete integration account.
5. **Given** a cloud AI request configured with an API key and custom athlete context notes or goals containing emails, IP addresses, or coordinates, **When** the request is dispatched, **Then** credentials are transmitted only in secure request headers (never in URLs or error text) and all PII is redacted from both workout payloads and coaching prompts.
6. **Given** a local AI server address pointing to a disallowed internal or metadata network address, **When** the user attempts to save or test that provider, **Then** the system rejects the address with a clear validation message.
7. **Given** workout titles, notes, athlete names, error messages, or AI-generated markdown containing raw HTML or script tags, **When** rendered on any interface (Gym Mode, Dashboard, AI Coach, Settings), **Then** the content is displayed strictly as safe text or sanitized formatting with zero script execution, reinforced by strict browser security headers (content security policy, clickjacking protection, and referrer suppression).
8. **Given** a deployment behind an HTTPS reverse proxy or a rotated/mismatched encryption key, **When** the user accesses Settings or initiates OAuth, **Then** forwarded protocol/host headers produce accurate HTTPS callback URLs and cookies when trusted, repeated failed login attempts are rate-limited, and unreadable encrypted secrets degrade gracefully into a clear "re-enter credentials" prompt rather than crashing the Settings screen.

---

### User Story 2 - Lossless Third-Party Sync and Accurate Endurance Telemetry (Priority: P1)

As an athlete syncing runs from Polar and erg sessions from Concept2, I want every historical and new workout to be captured accurately without data loss, silent failures, or distorted interval metrics.

**Why this priority**: Silent sync failures, premature remote queue commits, truncated pagination, and 10x interval duration errors directly corrupt or destroy athlete training records (P0 audit items).

**Independent Test**: Simulate multi-page Concept2 history, short intervals (<100 seconds), BikeErg sessions, Polar queue transactions where local persistence fails, expired tokens returning unauthorized errors, and concurrent manual + scheduled sync triggers.

**Acceptance Scenarios**:

1. **Given** new exercises waiting in a Polar transaction queue and a transient local database failure during save, **When** a sync runs, **Then** the remote Polar transaction is NOT committed, the sync audit log records a failed status without partial writes, and the workouts remain available for the next retry.
2. **Given** a Concept2 account with multiple pages of workout history, **When** a sync runs, **Then** the system fetches all pages before advancing the incremental sync watermark, leaving zero historical pages skipped or stuck.
3. **Given** an expired third-party access token or a provider outage (unauthorized, rate-limited, or server error), **When** a sync runs, **Then** the error is never reported as a zero-item success; authorization failures automatically trigger a token refresh and retry once, while unrecoverable errors record a failed audit status with details.
4. **Given** a Concept2 workout containing intervals or rest periods shorter than 100 seconds, or a BikeErg session, **When** normalized, **Then** all durations reflect exact seconds (never inflated 10x) and BikeErg pace is recorded as per-kilometer pace rather than mislabeled as a 500m rowing split.
5. **Given** a non-running Polar activity (e.g., cycling or rowing) or a re-synced workout whose update omits raw heart rate samples, **When** ingested, **Then** the activity is mapped to its appropriate discipline (or supported fallback) and existing computed heart rate zone durations are preserved rather than zeroed out.
6. **Given** multiple connected integration accounts where one account fails during a scheduled background sync, **When** the scheduled sync executes, **Then** remaining accounts still sync independently, and overlapping manual/scheduled syncs never produce duplicate workouts or race failures.
7. **Given** a third-party provider returning rate-limit or transient server errors, or an abrupt server restart mid-sync, **When** synchronization runs or the application restarts, **Then** transient errors are retried with bounded exponential backoff respecting provider retry windows, shutdown drains in-flight syncs cleanly within a bounded grace period, orphaned in-progress sync records are marked interrupted on startup, and recent sync failures are surfaced visibly on Settings.

---

### User Story 3 - Reliable Configuration Hub and Resilient Gym Voice Logging (Priority: P1)

As an athlete using my phone in the gym and configuring integrations from a browser, I want saving settings to preserve existing credentials, and I want voice or text strength logging to parse natural gym phrasing reliably, handle multiple exercises, survive page reloads and brief Wi-Fi drops, and never crash after demo or catalog seeding.

**Why this priority**: Currently, updating a secret on Settings corrupts the saved Client ID with mask characters, Gym Mode crashes after seeding demo data, multi-exercise dictation silently drops sets, and plain local-network mobile use breaks confirmation (P0/P1 audit items).

**Independent Test**: Seed demo data, update integration secrets and AI provider settings on the Settings screen, then log single-exercise, multi-exercise, bodyweight-weighted, kilogram, edited-exercise, and offline-buffered strength sets in Gym Mode across page reloads and non-HTTPS local network origins.

**Acceptance Scenarios**:

1. **Given** an already-configured integration on Settings, **When** the user views the page and updates only the Client Secret (or re-saves), **Then** masked preview values are displayed only as placeholders and never overwrite the stored Client ID with bullet characters.
2. **Given** an athlete switching between cloud and local AI providers on Settings, **When** they save a provider and reload the page, **Then** the saved provider is properly activated, its configuration persists visually after reload, and connection testing targets the active provider.
3. **Given** a database that has already been seeded with demo data or canonical exercises, **When** the athlete dictates and confirms sets for an existing exercise (e.g., Barbell Bench Press) in Gym Mode, **Then** the sets persist cleanly with zero duplicate-exercise errors.
4. **Given** natural spoken/typed strength phrasing without prepositions (e.g., `"bench press 225 lbs 3x5"`), phrasing with a metric default unit, or multi-clause phrasing (`"bench press 3x5 then pullups 3x10"`), **When** parsed and confirmed, **Then** weights, default units, and *all* exercises in the statement are accurately parsed, displayed for review, and committed idempotently without key collisions.
5. **Given** an unrecognized or gibberish transcript, **When** parsed, **Then** the system flags the entry as ambiguous and offers suggestions rather than silently forcing a low-confidence exercise match.
6. **Given** a staged strength entry where the athlete edits the exercise name before confirming, **When** confirmed, **Then** the set is saved under the edited exercise, and the voice audit log retains both the original parsed interpretation and the final confirmed values.
7. **Given** an active gym session on a mobile browser over a local network, **When** the athlete reloads the page, **Then** sets already logged in the active session remain visible with accurate total volume (converting kg to lbs and including added bodyweight load); and if network connectivity drops during confirmation, **Then** the submission is buffered locally and automatically synchronized once connectivity resumes.

---

### User Story 4 - Consistent Analytics, Honest Telemetry, and Scalable Performance (Priority: P2)

As an athlete reviewing months or years of multi-modal training data on the Dashboard and AI Coach, I want fast page loads, mathematically consistent metrics across every card, truthful telemetry visualizations, and clear validation feedback on bad inputs.

**Why this priority**: Loading full second-by-second heart rate history into memory on list/profile endpoints will exhaust memory as history grows; conflicting 1RM formulas, unsorted cross-year weeks, fabricated pace curves, and broken error banners erode athlete trust (P1 audit items).

**Independent Test**: Populate multi-year workout history with dense telemetry, load Dashboard across preset and custom windows, update the Heart Rate Profile, compare estimated 1RM between muscle group cards and PR showcase, inspect workouts with and without speed telemetry, and trigger validation/coaching errors.

**Acceptance Scenarios**:

1. **Given** hundreds of endurance workouts with dense per-second heart rate streams, **When** the athlete loads the Dashboard or updates their Heart Rate Zones Profile, **Then** the workouts list loads without fetching raw telemetry streams into memory, respects the selected time window (preset or custom), and heart rate zone recalculation completes in bounded batches without request timeouts or memory spikes.
2. **Given** strength sets logged across multiple exercises in a muscle group, **When** viewing the Resistance Volume table and the Personal Records showcase, **Then** both views use the exact same estimated 1RM calculation methodology, each muscle group's displayed estimated 1RM corresponds to its displayed top exercise (or is clearly attributed), and working-set counts exclude warmup sets.
3. **Given** endurance workouts spanning a calendar year boundary (e.g., December into January), **When** viewing weekly cardio trends, **Then** weeks appear in strict chronological order.
4. **Given** an outdoor run that lacks recorded speed or GPS telemetry, **When** opening its detail view, **Then** the system does not silently present heart-rate-derived fabricated pace as measured speed (either omitting pace or explicitly labeling it as estimated).
5. **Given** invalid inputs (e.g., resting heart rate higher than max heart rate, overlapping heart rate zones, out-of-range AI temperature/tokens, excessive page limits, or oversized GPX uploads), **When** submitted, **Then** the system rejects them cleanly with user-readable validation messages rather than unhandled server errors.
6. **Given** a failing coaching analysis request or an edit to a preset coaching philosophy on the AI Coach page, **When** executed, **Then** analysis errors render visibly in the UI (never throwing missing-element errors), and saving a philosophy preserves its description and primary modality.
7. **Given** a new athlete with fewer than four weeks of history requesting a forward training plan, **When** baseline weekly volume is calculated, **Then** the baseline reflects actual active weeks rather than artificially dividing by four, using consistent athlete-timezone date boundaries.
8. **Given** an athlete configured in a non-UTC local timezone (e.g., US Pacific) who completes a workout on Sunday evening, **When** viewing weekly Zone 2, VO2 Max, or Resistance charts and date-range filters, **Then** the workout is attributed to the athlete's local Sunday week rather than next Monday's UTC week.
9. **Given** an athlete double-clicking "Analyze Workout" or "Generate Plan", or an AI provider returning an out-of-bounds schedule (e.g., negative duration, out-of-range day offset, duplicate dates, or zero rest days when rest days are required), **When** processed, **Then** duplicate concurrent AI requests are prevented while one is in flight, and invalid generated schedules are rejected cleanly rather than persisted.

---

### User Story 5 - Training History Export, Daily Editing Controls, and Maintainable Architecture (Priority: P3)

As a long-term Coach3 owner, I want to export my complete training history at any time, edit or undo everyday workout entries, navigate a unified and accessible interface across all four screens, and rely on strong automated quality gates to prevent regressions.

**Why this priority**: Satisfies Constitution Principle I (irrevocable data exportability), closes daily-use friction gaps (editing notes, deleting mistaken sets, checking off planned workouts), eliminates frontend duplication and accessibility barriers, and ensures future changes are verified against real database migrations and static checks (P1 export + P2 items).

**Independent Test**: Export the athlete's complete training archive and verify all records are present; edit workout notes, delete a strength set, mark a planned workout complete, and paginate workout history; verify consistent navigation, pinch-to-zoom on mobile, and clean schema upgrade/downgrade tests against a real relational database.

**Acceptance Scenarios**:

1. **Given** an athlete with logged workouts, telemetry, strength sets, coaching philosophies, and training plans, **When** they initiate a full training history export, **Then** they receive a complete, portable export of all authentic athlete records.
2. **Given** an existing workout session, strength set, or scheduled coaching workout, **When** the athlete edits workout notes/title, deletes an erroneous strength set, or toggles completion on a planned workout, **Then** the change persists immediately and updates downstream analytics accurately.
3. **Given** any of the four web interfaces (Gym Mode, Dashboard, AI Coach, Settings) on mobile or desktop, **When** the user navigates between pages, **Then** all pages share consistent navigation, styling, notifications, a single unified AI provider settings experience, and allow standard mobile pinch-to-zoom accessibility.
4. **Given** the automated verification suite, **When** tests and static checks run before release, **Then** schema migrations (upgrade and downgrade) are validated against the target production relational database engine, deprecation warnings are surfaced rather than silenced, and static analysis catches missing imports, dead code, and security anti-patterns automatically.
5. **Given** an athlete or operator troubleshooting a failed sync or AI error, **When** inspecting Settings or application logs, **Then** Settings displays a System Health & Sync Diagnostics panel (database connectivity, scheduler status, next scheduled sync, and recent sync audit outcomes/errors), and logs are structured with per-request correlation identifiers and zero leaked credentials.

---

### Edge Cases

- **Missing or corrupted external IDs**: What happens when a third-party provider payload omits an activity ID? The adapter rejects the malformed record with a logged diagnostic instead of storing `"None"` as a unique external ID.
- **Repeated single-set multi-exercise commits**: What happens when a user logs two distinct exercises with 1 set each in a single voice submission (`"1x5 deadlift then 1x10 dips"`)? Every created set receives a distinct deterministic sub-key derived from the submission's idempotency key so neither collides with the other or with prefix-similar keys (`"key_1"` vs `"key_10"`).
- **Zero-telemetry or metadata-only re-sync**: What happens when Polar or Concept2 re-sends a workout summary (e.g., edited title) without heart rate samples? Existing stored heart rate samples and computed Zone 1–5 durations remain intact.
- **Unsecured LAN mobile browser context**: What happens when an athlete accesses Coach3 from an iPhone over `http://192.168.x.x:8000` where browser secure-context APIs (random UUID generation, clipboard) are unavailable? Fallback utilities allow set confirmation and URL copying to succeed without runtime errors, while guiding the user if voice dictation requires HTTPS.
- **Athlete with very low resting HR**: What happens when a well-trained endurance athlete enters a resting heart rate of 30 bpm (or 28 bpm)? Validation allows physiologically realistic resting heart rates (e.g., ≥ 25 bpm) while still rejecting impossible values.
- **Database unreachable during health check**: What happens when the application container is running but the database is stopped or unreachable? The health endpoint reports an unhealthy/degraded status rather than returning a false healthy signal.
- **Concurrent first-boot requests**: What happens when two browser tabs hit the application simultaneously on a fresh database? Only a single default athlete record is created (no duplicate user rows).
- **Oversized or malformed GPX uploads**: What happens when a user uploads a corrupted XML file, an entity-expansion XML payload, or a file exceeding the maximum size limit? The system safely rejects the upload with a clear error and bounded memory usage.
- **Rotated or mismatched encryption key**: What happens when the application starts with a different encryption key than the one used to encrypt previously saved integration or AI credentials? The system catches decryption failures gracefully, flags affected credentials as requiring re-entry on Settings, and never bricks the Settings or Dashboard UI.
- **Process crash or host reboot mid-sync**: What happens if the server restarts while a Polar or Concept2 sync is in progress? On next startup, orphaned in-progress sync audit records are transitioned to failed/interrupted so status displays remain truthful and subsequent syncs proceed cleanly.
- **Sunday evening workout in negative UTC offsets**: What happens when an athlete in US Pacific time logs a workout at 6:00 PM Sunday (Monday 02:00 UTC)? Weekly volume charts and daily filters assign the workout to the athlete's configured local calendar day and week, not UTC Monday.
- **Duplicate mobile taps on slow AI inference**: What happens when an athlete taps "Analyze Workout" or "Generate Plan" twice while a cloud or local model is still generating? The interface disables duplicate submission and the backend rejects or coalesces concurrent duplicate requests so cloud quota is not wasted and local inference hardware is not overloaded.

## Requirements *(mandatory)*

### Functional Requirements

#### Security, Privacy & Deployment (P0)

- **FR-001**: System MUST boot cleanly on all declared supported runtime versions (including the containerized deployment runtime) with zero import-time or startup errors.
- **FR-002**: Containerized deployment MUST automatically apply pending database schema migrations on startup, run the application process as a non-privileged user, expose a dependency-aware health check, and restrict database ports to local/private host interfaces by default.
- **FR-003**: System MUST require an explicit, valid encryption key in non-test environments and MUST NOT fall back to any hardcoded default encryption key.
- **FR-004**: System MUST restrict cross-origin browser requests to explicitly configured trusted origins and MUST NOT combine wildcard origins with credentialed requests.
- **FR-005**: System MUST protect all application data, configuration, coaching, and administrative actions with a built-in single-user passphrase sign-in backed by a long-lived, script-inaccessible, cross-site-protected session (required whenever deployed beyond localhost, with an explicit opt-in bypass permitted only for local loopback development), including explicit sign-in and sign-out controls.
- **FR-006**: System MUST generate, store with expiration, and strictly verify OAuth2 `state` nonces on all third-party integration authorization callbacks to prevent cross-site account-linking attacks.
- **FR-007**: System MUST transmit external AI provider API keys exclusively via secure request headers (never in request URLs) and MUST sanitize error/diagnostic outputs so secrets never appear in logs or UI responses.
- **FR-008**: System MUST validate user-supplied local AI endpoint URLs against allowed schemes and block disallowed internal/cloud-metadata network targets to prevent server-side request forgery.
- **FR-009**: System MUST scrub personally identifiable information (emails, IP addresses, phone numbers, raw coordinate literals) from *all* outbound cloud AI content—including workout payloads, custom athlete context notes, and planning target goals—before transmission.
- **FR-010**: All web interfaces MUST safely escape or sanitize all dynamic, user-supplied, third-party, and AI-generated content prior to browser rendering so injected markup or scripts cannot execute.

#### Third-Party Sync & Data Integrity (P0/P1)

- **FR-011**: Polar synchronization MUST defer remote transaction commitment until all fetched workouts and telemetry in that transaction have been durably committed to local storage.
- **FR-012**: Third-party sync adapters MUST propagate network, rate-limit, server, and authorization errors rather than returning empty successful batches; sync orchestration MUST refresh tokens specifically on authorization failure, roll back failed partial transactions cleanly, and record accurate failure audit logs.
- **FR-013**: Paginated sync adapters (Concept2) MUST iterate through all available pages in a sync cycle before advancing the incremental sync watermark and clearing the pagination cursor.
- **FR-014**: Concept2 normalization MUST accurately convert all work, interval, and rest durations from tenths of a second regardless of length (including durations under 100 seconds) and MUST record BikeErg pace as per-kilometer pace rather than per-500m rowing split.
- **FR-015**: Third-party adapters MUST validate presence of external activity identifiers and map provider sport types accurately rather than defaulting non-running Polar activities to outdoor runs.
- **FR-016**: Workout ingestion MUST preserve previously calculated heart rate zone durations during metadata-only re-syncs that lack heart rate samples, handle concurrent sync runs idempotently without duplicate-record conflicts, and persist dense telemetry streams efficiently in bulk.
- **FR-017**: Scheduled background synchronization MUST isolate processing per integration account so one failing account cannot disrupt others, and guard against duplicate execution across multiple application workers.

#### Configuration & Gym Mode Ergonomics (P0/P1)

- **FR-018**: Settings configuration MUST render masked integration Client IDs solely as non-submittable placeholders so saving or rotating a Client Secret never overwrites the real Client ID with mask characters.
- **FR-019**: AI inference provider configuration MUST be consolidated into a consistent experience that loads existing provider state on page load, activates newly saved/selected providers reliably, and tests the active provider accurately.
- **FR-020**: Exercise catalog identifiers MUST remain consistent across static definitions, initial seeding, demo seeding, voice parsing, and set persistence so committing sets never triggers duplicate-exercise or broken-reference errors.
- **FR-021**: Gym Mode set persistence MUST enforce exact idempotency per submission across single-set, multi-set, and multi-exercise payloads without prefix-matching collisions or multi-candidate key clashes.
- **FR-022**: Gym Mode natural language parsing MUST extract weights with or without leading prepositions, honor the configured default weight unit when omitted, and mark unrecognized transcripts as ambiguous rather than forcing a low-confidence exercise match.
- **FR-023**: Gym Mode UI MUST display and commit all exercises from multi-clause statements, honor user edits to the exercise name before committing, preserve both original parsed output and confirmed values in voice audit logs, restore today's logged sets on page reload, accurately calculate session volume across units and weighted bodyweight movements, and operate without errors over non-HTTPS local network origins.
- **FR-024**: Gym Mode UI MUST buffer unsubmitted strength sets locally during transient network dropouts and automatically synchronize them once the server becomes reachable.

#### Analytics, Performance & Validation (P1)

- **FR-025**: Workout listing MUST determine telemetry presence, interval status, and working-set counts (excluding warmups) without loading raw per-second heart rate streams into memory, and MUST filter by the active athlete, active status, and selected date window (both presets and custom ranges).
- **FR-026**: Updating the athlete's Heart Rate Zones Profile MUST recalculate historical workout zones in bounded batches or asynchronously without loading all historical heart rate samples into memory at once.
- **FR-027**: Exercise catalog queries MUST NOT eagerly load full historical strength sets for every exercise.
- **FR-028**: All analytics and personal record views MUST use a single canonical estimated 1RM formula (Epley, capped at 10 or fewer reps), accurately attribute each muscle group's estimated 1RM to its corresponding lift, and sort weekly cardio trends chronologically across year boundaries.
- **FR-029**: Workout detail telemetry MUST NOT disguise synthetically generated pace (inferred from heart rate) as measured speed telemetry without explicit labeling.
- **FR-030**: System MUST validate all incoming request payloads—including heart rate profile zone ordering and physiological bounds (resting HR ≥ 25 bpm and < max HR), coaching parameter bounds, bounded query limits, and safe bounded GPX XML uploads—returning clear validation errors instead of server failures.
- **FR-031**: AI Coach UI MUST display analysis errors cleanly in a visible interface error banner, verify request success before activating saved providers, preserve philosophy descriptions and modalities on edit, and compute forward-plan baseline weekly volume accurately from actual active weeks using the athlete's configured timezone.

#### Data Export, Daily Usability & Quality Standards (P1/P2)

- **FR-032**: System MUST provide a single-action downloadable ZIP archive exporting 100% of authentic athlete records, containing both a lossless structured JSON full backup (workouts, second-by-second heart rate and GPS telemetry, splits, strength sets, exercise catalog mappings, personal records, coaching philosophies, critiques, and training plans) and clean CSV summary tables (workouts and strength sets) ready for spreadsheet analysis.
- **FR-033**: System MUST support everyday training record management: editing workout titles and notes, deleting mistakenly logged strength sets, toggling completion status on scheduled coaching workouts, and paginating through workout history.
- **FR-034**: Web interfaces MUST share unified navigation, styling, and notification patterns and MUST allow mobile pinch-to-zoom accessibility across all pages.
- **FR-035**: Persistent data structures and schema upgrades MUST enforce clean integrity rules (including at most one active AI provider and one active philosophy per athlete, unbounded encrypted secret storage, clean reversible upgrades, and removal of redundant constraints), and either populate or remove unused personal-record storage structures.
- **FR-036**: Application workflows MUST enforce consistent single-owner transactional boundaries, a single race-safe default athlete and heart-rate profile initialization path, and efficient reuse of external provider connections.
- **FR-037**: Automated verification MUST include real-database upgrade/downgrade and integration tests, surface deprecation warnings, isolate test state cleanly, and enforce automated static quality checks and reproducible builds.

#### Operational Resilience, Timezone Accuracy & Observability (Systems Engineering Additions)

- **FR-038**: Athlete profile MUST support a configurable display timezone (IANA timezone name, editable in Settings) and all weekly volume buckets, daily session boundaries, and custom date-range filters MUST evaluate boundaries in the athlete's configured timezone rather than raw UTC.
- **FR-039**: System MUST handle encrypted credential decryption failures gracefully (surfacing a clear "re-enter credentials" state instead of failing page loads), recover orphaned in-progress sync audit entries as interrupted/failed on startup, and drain in-flight background sync jobs and database connections cleanly within a bounded grace period on shutdown.
- **FR-040**: System MUST apply strict browser defense-in-depth security headers across all pages (including content security policy blocking unauthorized inline script execution, clickjacking protection, MIME-sniffing protection, and referrer suppression so OAuth callback URLs never leak).
- **FR-041**: System MUST support trusted reverse-proxy deployments (honoring forwarded protocol and host headers when explicitly enabled) so OAuth redirect URLs and secure session cookies work reliably behind HTTPS termination, and MUST rate-limit repeated failed sign-in attempts with progressive backoff when authentication is enabled.
- **FR-042**: Third-party sync and external AI requests MUST enforce bounded per-request and total operation timeouts and perform bounded exponential backoff retries on transient server or rate-limit responses while honoring provider retry-after guidance.
- **FR-043**: AI analysis and schedule-generation workflows MUST prevent concurrent duplicate inferences for the same athlete while a generation is already in flight, and MUST validate generated schedules against safety and structural invariants (valid horizon day offsets, non-duplicate dates, sane non-negative workout durations, and required minimum rest days) before persisting.
- **FR-044**: System MUST emit structured logs carrying per-request correlation identifiers with automatic redaction of credentials, tokens, and API keys, and MUST display a System Health & Sync Diagnostics section on Settings showing database health, scheduler status, next scheduled sync time, and recent sync audit outcomes/errors (with a visible warning indicator when recent syncs fail).

### Key Entities

- **Athlete Session / Access Credential**: Represents authenticated single-user access state for self-hosted operation and CSRF-protected OAuth state nonces with bounded lifetimes.
- **Integration Sync Watermark & Transaction State**: Represents the durable pagination cursor, last successful sync timestamp, and remote transaction lifecycle ensuring remote queues are acknowledged only after local persistence.
- **Voice Audit Record**: Represents a strength logging event capturing raw transcript, original pre-edit parsed candidates, edit status, and final confirmed sets.
- **Offline Pending Set Queue**: Represents locally buffered strength set submissions on the mobile client awaiting synchronization with idempotency guarantees.
- **Training History Export Archive**: Represents a portable, self-contained snapshot of all authentic athlete records (workouts, telemetry, strength sets, personal records, coaching philosophies, critiques, and plans).
- **Athlete Timezone Preference**: Represents the athlete's configured IANA timezone used to derive accurate local calendar days and weekly aggregation boundaries.
- **System Diagnostics Snapshot**: Represents real-time operational health including database reachability, encryption key readability per integration, background scheduler state, and recent sync audit outcomes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A clean containerized deployment from an empty database boots and passes its dependency-aware health check in under 30 seconds with zero manual migration steps and zero startup errors on the target runtime.
- **SC-002**: 100% of verified security tests pass: unauthenticated/untrusted cross-origin requests are blocked, tampered OAuth callbacks are rejected, zero secrets appear in outbound URLs, logs, or error payloads, zero PII escapes into outbound cloud AI prompts, strict browser security headers are present on every page, and zero HTML/script injection payloads execute across all four interfaces.
- **SC-003**: 100% of simulated multi-page syncs, short-interval (<100s) Concept2 sessions, BikeErg sessions, transient rate-limit/5xx responses, and transient DB failures during Polar sync result in zero lost workouts, zero duplicate sessions, and exact metric fidelity.
- **SC-004**: 100% of Gym Mode flows (single-exercise, multi-clause, edited exercise name, metric/imperial, weighted bodyweight, post-demo-seeding, page reload, and offline-then-online reconnect) persist accurately without errors.
- **SC-005**: Loading the Dashboard workout list with 200+ workouts containing dense per-second telemetry completes in under 500 ms with bounded memory usage (zero raw telemetry rows fetched for the list view), and updating Heart Rate Zones across multi-year history completes without timeouts or memory exhaustion.
- **SC-006**: Estimated 1RM values and working-set counts match 100% identically across all Dashboard cards, tables, and Personal Records views for the same underlying workout data, and 100% of workouts logged near midnight/week boundaries bucket into the athlete's configured local calendar day and week.
- **SC-007**: Athletes can export 100% of their authentic training history in a single action and edit notes, undo strength sets, or check off scheduled workouts in under 10 seconds per action.
- **SC-008**: The full automated verification suite—including static analysis, type checks, unit/contract tests, and real-database migration upgrade/downgrade tests—passes with zero errors and zero suppressed deprecation warnings.
- **SC-009**: Recovering from a simulated encryption key mismatch, mid-sync crash/restart, or concurrent double-submission of AI coaching requests completes with zero page crashes, zero permanently stuck sync records, and zero duplicate concurrent AI executions.
- **SC-010**: Any failed background sync is visible in the Settings System Health & Sync Diagnostics panel within one page refresh, and every request log entry carries a correlation identifier with zero unredacted secrets.

## Assumptions

- Coach3 remains a self-hosted, single-athlete application (multi-tenant SaaS user management is out of scope, though data remains scoped cleanly by athlete ID to prevent cross-record leaks).
- Users running Coach3 on a home network may access the web UI from an iPhone over plain HTTP LAN IP or behind a local HTTPS reverse proxy (e.g., Tailscale/Caddy); voice dictation relies on browser capabilities that require HTTPS on iOS, while text input and confirmation MUST work cleanly even over plain HTTP LAN access.
- Demo workout records remain strictly isolated from authentic athlete records and are excluded from authentic athlete exports by default (or clearly flagged if included).
- Existing authentic athlete databases upgraded from prior releases MUST be preserved losslessly during all schema remediation upgrades.
