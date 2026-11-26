---
description: "Dependency-ordered implementation tasks for Coach3 comprehensive remediation (007-remediation)"
---

# Tasks: Comprehensive Security, Data Integrity, Reliability, and Quality Remediation

**Input**: Design documents from `/specs/007-remediation/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/api-remediation.yaml](contracts/api-remediation.yaml), [quickstart.md](quickstart.md)

**Tests**: Included per Constitution Quality Standards (`FR-037`, `SC-002`–`SC-010`) so every P0, P1, P2, and systems-engineering fix is permanently regression-guarded.

**Organization**: Tasks are grouped by user story (`US1`–`US5`) in priority order (`P1 → P2 → P3`), mapping all P0, P1, and P2 audit findings plus systems-engineering additions into independently testable increments.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story mapping (`[US1]`–`[US5]`) — omitted in Setup, Foundational, and Polish phases
- Exact repository file paths are included in every task

---

## Phase 1: Setup & Static Quality Gates

**Purpose**: Tooling, reproducible dependencies, immediate Python 3.12 crash fix, and clean test isolation.

- [X] T001 Update `pyproject.toml` to add `defusedxml` runtime dependency, add `ruff` and `mypy` to `[project.optional-dependencies].dev`, configure `[tool.ruff]` (including Bandit security rules `S`) and `[tool.mypy]`, set `asyncio_default_fixture_loop_scope = "function"`, and remove `ignore::DeprecationWarning` from `filterwarnings`
- [X] T002 Fix Python 3.11–3.13 startup `NameError` by importing `Any` from `typing` in `src/services/gym_parser.py` and generate pinned dependency lockfile in `requirements.lock`
- [X] T003 [P] Update `.env.example` to remove the hardcoded default `ENCRYPTION_KEY` value and document `COACH3_PASSPHRASE`, `AUTH_DISABLED_LOCALHOST`, `ALLOWED_ORIGINS`, `TRUST_PROXY_HEADERS`, `ALLOWED_LLM_HOSTS`, and `SCRUB_TERMS`
- [X] T004 [P] Update `tests/conftest.py` to add an `autouse` `app.dependency_overrides.clear()` fixture, inject an ephemeral Fernet `ENCRYPTION_KEY` for test runs, and enable localhost test auth handling cleanly

---

## Phase 2: Foundational Infrastructure & Schema Remediation

**Purpose**: Core configuration, security primitives, structured logging, HTTP client resilience, shared dependencies, ORM/schema cleanup, migration `006`, and shared frontend shell that ALL user stories depend on.

**⚠️ CRITICAL**: Complete Phase 2 before starting User Story phases.

- [X] T005 Harden `src/core/config.py` to remove the hardcoded `ENCRYPTION_KEY` default, require a valid 32-byte url-safe base64 Fernet `ENCRYPTION_KEY` when `ENVIRONMENT != "test"`, and add typed settings for `COACH3_PASSPHRASE`, `COACH3_PASSPHRASE_HASH`, `AUTH_DISABLED_LOCALHOST`, `ALLOWED_ORIGINS`, `TRUST_PROXY_HEADERS`, `ALLOWED_LLM_HOSTS`, `SCRUB_TERMS`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_STATEMENT_TIMEOUT_MS`, and `SYNC_PAGE_LIMIT`
- [X] T006 [P] Update `src/core/security.py` to add `validate_encryption_key()` and `decrypt_token_safe()` that catches `cryptography.fernet.InvalidToken` and returns structured `(plaintext, decryption_error)` instead of crashing
- [X] T007 [P] Implement structured JSON logging with `request_id` contextvar propagation and a credential/token/API-key/passphrase redaction filter in `src/core/logging.py`
- [X] T008 [P] Implement shared `httpx.AsyncClient` lifecycle helpers, bounded exponential backoff + jitter retry helper honoring `Retry-After` on `429`/`502`/`503`/`504`/timeouts, and SSRF `validate_endpoint_url()` guard (HTTP/HTTPS only; blocks `169.254.0.0/16`, `fe80::/10`, `0.0.0.0/8`, and enforces optional `ALLOWED_LLM_HOSTS`) in `src/core/http_client.py`
- [X] T009 [P] Update `src/core/database.py` to configure engine pool bounds (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`), PostgreSQL `statement_timeout`, and expose `dispose_engine()` for clean shutdown
- [X] T010 [P] Create single race-safe `get_or_create_default_user()` and unified `get_or_create_default_hr_profile()` (`max_hr=185`, `resting_hr=50`, 50/60/70/80/90/100% zones) helpers in `src/core/deps.py`
- [X] T011 [P] Update `src/models/user.py` to add `timezone: String(64)` (`nullable=False`, `default="UTC"`, `server_default="UTC"`) and `passphrase_hash: Text` (`nullable=True`) on `User`, update `UserHeartRateProfile` `check_hr_bounds` to `resting_hr >= 25 AND resting_hr < 150 AND max_hr > 120 AND max_hr < 240 AND resting_hr < max_hr`, and add `check_hr_zones_ordered` (`zone1_min > 0 AND zone1_min < zone1_max AND zone1_max <= zone2_min AND zone2_min < zone2_max AND zone2_max <= zone3_min AND zone3_min < zone3_max AND zone3_max <= zone4_min AND zone4_min < zone4_max AND zone4_max <= zone5_min AND zone5_min < zone5_max`)
- [X] T012 [P] Update `src/models/integration.py` to add `OAuthState` (`state: String(128)` PK, `user_id: UUID` FK `users.id` `ON DELETE CASCADE` `nullable=False`, `provider: String(50)` `CHECK (provider IN ('polar', 'concept2'))`, `expires_at: DateTime(timezone=True)` indexed `nullable=False`, `created_at: DateTime(timezone=True)` `nullable=False`), standardize `JSON_TYPE = JSON().with_variant(JSONB, "postgresql")`, and remove redundant `index=True` on `IntegrationClientConfig.provider`
- [X] T013 [P] Update `src/models/exercise.py`, `src/models/strength_set.py`, `src/models/workout.py`, and `src/models/voice_log.py` to change `StrengthExercise.sets`, `WorkoutSession.strength_sets`, and `WorkoutSession.voice_logs` from `lazy="selectin"` to `lazy="select"`, add `submission_key: String(100)` (`nullable=True`, indexed `idx_strength_set_submission`) and `idempotency_key: String(120)` on `StrengthSet`, standardize `JSON_TYPE`, and remove duplicate unique indexes on already-unique columns
- [X] T014 [P] Update `src/models/coaching.py` to alter `LLMProviderConfig.api_key_encrypted` from `String(500)` to `Text`, add PostgreSQL partial unique indexes `uq_llm_provider_active_user` and `uq_coaching_philosophy_active_user` (`WHERE is_active = true`), add check constraints on `CoachingPhilosophy` (`target_zone2_pct >= 0 AND target_zone2_pct <= 100`, `max_rpe_threshold >= 1 AND max_rpe_threshold <= 10`, `min_rest_days_per_week >= 0 AND min_rest_days_per_week <= 7`, `primary_modality IN ('endurance', 'strength', 'hybrid')`), and remove dead `src/models/personal_record.py` and its export from `src/models/__init__.py`
- [X] T015 Fix `alembic/versions/002_gym_mode_schema.py` to replace bare `except Exception: pass` with an explicit PostgreSQL dialect check, convert `default=` to `server_default=` on table columns, and restore `check_discipline_valid` in `downgrade()`
- [X] T016 Create lossless, fully reversible migration `alembic/versions/006_remediation_hardening.py` (revising `005_integration_config_and_demo`) applying all schema additions, constraints, partial unique indexes, redundant-index drops, and dead `personal_records` table removal from T011–T014 with full restoration in `downgrade()`
- [X] T017 Create shared CSP-compliant frontend foundation in `src/static/css/common.css` and `src/static/js/common.js` (unified theme variables, single shared navbar with Sign Out action, toast helper, `escapeHtml()`, HTML-escaping `formatMarkdown()`, non-HTTPS-safe `safeUUID()` and `safeCopy()`, and `authFetch()` redirecting to `/login` on `401`)

**Checkpoint**: Foundation ready — database schema, security primitives, logging, HTTP resilience, and shared frontend shell are in place for all 5 user stories.

---

## Phase 3: User Story 1 - Hardened Deployment, Access Security, and Data Sovereignty (Priority: P1) 🎯 MVP

**Goal**: Make Coach3 safe to boot and expose on a home network: mandatory encryption key, built-in single-user passphrase login + brute-force rate limit, strict CORS + CSP security headers, OAuth2 CSRF `state` verification, SSRF & header-only Gemini key protection, full PII scrubbing across all prompts, and non-root Docker container with automatic migration entrypoint and DB-aware `/health`.

**Independent Test**: Boot cleanly with empty DB and valid key; confirm missing key fails startup; confirm unauthenticated & untrusted-origin requests fail; confirm brute-force login hits `429`; confirm forged OAuth `state` is rejected; confirm SSRF metadata URL is rejected; confirm Gemini key never appears in URLs/errors; confirm PII in notes/goals is redacted; confirm XSS payloads never execute under `script-src 'self'` CSP.

### Implementation for User Story 1

- [X] T018 [P] [US1] Implement `scrypt` passphrase hashing/verification (`hmac.compare_digest`), HMAC-SHA256 `coach3_session` cookie signing/verification (`HttpOnly`, `SameSite="lax"`, `Secure` on HTTPS, 30-day TTL), localhost-only dev bypass guard (`AUTH_DISABLED_LOCALHOST`), and per-IP sliding-window brute-force rate limiter (`429` + `Retry-After`) in `src/core/auth.py`
- [X] T019 [P] [US1] Create `LoginRequest` and `AuthStatusResponse` schemas in `src/schemas/auth.py` and implement `GET /api/v1/auth/status`, `POST /api/v1/auth/login`, and `POST /api/v1/auth/logout` in `src/api/auth.py`
- [X] T020 [P] [US1] Create CSP-compliant login interface in `src/static/login.html` and `src/static/js/login.js` with accessible `width=device-width, initial-scale=1.0` viewport
- [X] T021 [P] [US1] Extend `PrivacyScrubberService` in `src/core/privacy.py` to scrub emails, IPv4/IPv6 addresses, phone numbers, raw decimal GPS coordinate pairs, and configured `SCRUB_TERMS`, and scrub `philosophy.custom_context_notes`, `philosophy.name`, and `target_goal` in `src/services/coaching_service.py`
- [X] T022 [P] [US1] Harden `src/services/llm_client.py` to pass Gemini API key exclusively via `x-goog-api-key` header (zero `?key=` in URLs), validate `LlamaCppClient` `endpoint_url` with `validate_endpoint_url()`, sanitize exception strings before returning/logging, and enforce timeouts/backoff via `src/core/http_client.py`
- [X] T023 [US1] Implement DB-backed single-use expiring OAuth2 `state` CSRF generation (`GET /{provider}/auth-url`), atomic validation & deletion (`GET /{provider}/callback`), and graceful `InvalidToken` handling in `src/api/integrations.py`
- [X] T024 [US1] Harden `src/main.py` and `src/api/router.py` to mount `auth` router, enforce authentication middleware across `/api/v1/*` and HTML pages (excluding `/health`, `/login`, `/static/*`, `/api/v1/auth/login`, `/api/v1/auth/status`, and OAuth callbacks), lock down `CORSMiddleware` to `settings.ALLOWED_ORIGINS` (never `*` with credentials), add browser security headers middleware (`Content-Security-Policy` with `script-src 'self'`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`), add `X-Request-ID` structured logging middleware, support trusted reverse-proxy headers, add `GET /login`, and upgrade `GET /health` to execute `SELECT 1` returning `200` or `503`
- [X] T025 [P] [US1] Create `docker-entrypoint.sh` (runs `alembic upgrade head` then `exec uvicorn` with `--proxy-headers` when `TRUST_PROXY_HEADERS=true`), harden `Dockerfile` (non-root `coach3` user, single `src/` layout without duplicate copy, `HEALTHCHECK` against `/health`, entrypoint), and harden `docker-compose.yml` (`127.0.0.1:${POSTGRES_PORT:-5432}:5432` bind, required `ENCRYPTION_KEY:?`, pass `COACH3_PASSPHRASE`, `ALLOWED_ORIGINS`, `TRUST_PROXY_HEADERS`, `POLAR_REDIRECT_URI`, `CONCEPT2_REDIRECT_URI`, `SYNC_INTERVAL_MINUTES`)

### Tests for User Story 1

- [X] T026 [P] [US1] Add security & authentication tests in `tests/unit/test_auth_and_security.py` covering missing `ENCRYPTION_KEY` startup validation, passphrase login/logout/cookie flags, brute-force `429` + `Retry-After`, CORS rejection of untrusted origins, security headers & CSP, SSRF blocking of `169.254.169.254`, Gemini `x-goog-api-key` header without URL leakage, graceful `InvalidToken` handling, and DB-aware `/health` (`200` & `503`)
- [X] T027 [P] [US1] Expand `tests/unit/test_privacy.py` to verify phone/GPS/custom-term scrubbing and zero PII leakage inside `CoachingService.build_analysis_system_prompt()`, `build_planning_system_prompt()`, and planning user prompts
- [X] T028 [P] [US1] Add OAuth2 CSRF `state` integration tests in `tests/integration/test_oauth_csrf.py` verifying missing, forged, expired, and replayed `state` callbacks are rejected while valid single-use `state` succeeds

**Checkpoint**: User Story 1 (MVP security & hardened deployment) is complete and independently verifiable.

---

## Phase 4: User Story 2 - Lossless Third-Party Sync and Accurate Endurance Telemetry (Priority: P1)

**Goal**: Eliminate every workout loss and telemetry corruption bug across Polar and Concept2 syncing: deferred Polar commit, honest HTTP error propagation + 401-only token refresh, full Concept2 pagination, exact tenths-of-second & BikeErg math, Polar sport mapping, zone preservation on soft-sync, bulk upserts, and isolated/graceful scheduling.

**Independent Test**: Run simulated Polar transaction with DB failure (verify no remote commit), 3-page Concept2 history sync (verify all 3 pages imported before watermark advance), short `<100s` Concept2 intervals & BikeErg workouts (verify exact durations & km pace), expired 401 refresh, 429/503 backoff, metadata-only re-sync preserving zones, and startup recovery of orphaned `"running"` sync logs.

### Implementation for User Story 2

- [X] T029 [P] [US2] Add `pending_commit_token: dict[str, Any] | None = None` to `SyncBatchResult` and add async `commit_batch(self, access_token: str, commit_token: dict[str, Any]) -> None` (default no-op) on `BaseIngestionAdapter` in `src/adapters/base.py`
- [X] T030 [P] [US2] Remediate `src/adapters/polar.py` to move `PUT {tx_url}/{transaction_id}` out of `fetch_workouts_batch` into `commit_batch()`, propagate `httpx.HTTPError` using retry/backoff helper from `src/core/http_client.py`, validate non-empty `id` (never `"None"`), map Polar `sport`/`detailed-sport-info` to canonical disciplines, and parse GPX safely via `defusedxml.ElementTree`
- [X] T031 [P] [US2] Remediate `src/adapters/concept2.py` to convert all tenths-of-second durations (`time`, `rest_time`) unconditionally without the `> 1000` magic threshold, map BikeErg `pace` to `avg_pace_sec_per_km` (not `avg_split_sec_per_500m`), validate non-empty `id`, and propagate `httpx.HTTPError` using retry/backoff helper from `src/core/http_client.py`
- [X] T032 [US2] Remediate `src/services/ingestion.py` to preserve existing `zone1_duration_sec`–`zone5_duration_sec` when updating a workout with empty `heart_rate_samples`, use PostgreSQL `ON CONFLICT (provider, external_id) DO UPDATE` upsert (with SQLite fallback) to prevent concurrency races, and insert `HeartRateSample`/`GPSRoutePoint` rows in bulk via `session.execute(insert(...), rows)`
- [X] T033 [US2] Remediate `src/services/sync_service.py` to loop `while has_more` (bounded by `settings.SYNC_PAGE_LIMIT`) before clearing `account.sync_cursor` and updating `account.last_sync_at`, trigger OAuth token refresh strictly on `httpx.HTTPStatusError` with `status_code == 401`, invoke `adapter.commit_batch()` ONLY after `await db.commit()` succeeds, roll back failed transactions cleanly before persisting a failed `SyncAuditLog`, and use `get_or_create_default_hr_profile()` from `src/core/deps.py`
- [X] T034 [US2] Harden `src/core/scheduler.py` and `src/main.py` lifespan to isolate each integration account in its own `async_session_factory()` session, acquire a PostgreSQL advisory lock (`pg_try_advisory_lock`) around scheduled runs, recover orphaned `SyncAuditLog` rows with `status == "running"` to `status = "failed"` on startup, prune old `SyncAuditLog` rows (>90 days keeping latest 50/provider), drain active sync jobs gracefully on shutdown, and call `await dispose_engine()`

### Tests for User Story 2

- [X] T035 [P] [US2] Update `tests/unit/test_polar_adapter.py` to test deferred `commit_batch()`, Polar sport-type mapping, missing-ID rejection, HTTP error propagation, and `defusedxml` malformed/entity-expansion rejection
- [X] T036 [P] [US2] Update `tests/unit/test_concept2_adapter.py` to test short intervals (`time=600` → `60.0s`, `rest_time=900` → `90.0s`), BikeErg km pace mapping, missing-ID rejection, and HTTP error propagation
- [X] T037 [US2] Add sync resilience integration tests in `tests/integration/test_sync_resilience.py` covering Polar DB failure skipping `commit_batch()`, Concept2 3-page pagination + watermark semantics, 401 refresh + retry, transient 429/503 backoff, clean rollback + failed audit log, metadata-only soft-sync preserving HR zones, multi-account isolation, and startup orphan `"running"` recovery

**Checkpoint**: User Story 2 (lossless sync & telemetry fidelity) is complete and independently verifiable.

---

## Phase 5: User Story 3 - Reliable Configuration Hub and Resilient Gym Voice Logging (Priority: P1)

**Goal**: Prevent `/config` from overwriting Client IDs with bullets, fix AI provider load/save/activation on `/config`, unify exercise UUIDs so Gym Mode works cleanly after seeding, fix `GymParser` phrasing/ambiguity bugs, support multi-clause review/editing/reload/offline buffering in `/gym`, and fix exact submission idempotency & voice audit diffing.

**Independent Test**: Seed demo data, rotate a Polar Client Secret without losing Client ID, switch & reload AI providers on `/config`, parse and confirm multi-clause & preposition-less & kg & edited-exercise & offline-queued gym sets on `/gym`, and reload `/gym` to verify session restoration.

### Implementation for User Story 3

- [X] T038 [P] [US3] Harden `src/schemas/config.py`, `src/services/config_service.py`, and `src/api/config.py` to make `client_id` optional when updating `client_secret` on an existing DB config, reject any credential input containing mask bullets (`•`), catch `InvalidToken` via `decrypt_token_safe()` returning `decryption_error=True` on `ProviderConfigSummary`, sanitize error messages, and remove internal service commits
- [X] T039 [P] [US3] Unify deterministic `uuid5(NAMESPACE_DNS, f"coach3.exercise.{slug}")` exercise IDs across `src/services/exercise_catalog.py`, `src/scripts/seed_exercises.py` (also remove duplicate `"smith squat"` alias and track new aliases without triggering async lazy loads), and `src/services/seed_service.py`, and call `await catalog_service.load_from_db()` during `src/main.py` lifespan startup
- [X] T040 [P] [US3] Remediate `src/services/gym_parser.py` to parse bare `<weight> <unit>` without leading prepositions (e.g., `"bench press 225 lbs 3x5"`, `"225lb squat 5x5"`), honor `default_unit` when unit is omitted, stop forcing low-confidence alternatives when `best_score < min_score` (returning `None` candidate + `is_ambiguous=True`), and remove dead `weight_match` variable
- [X] T041 [US3] Remediate `src/schemas/gym.py` and `src/api/gym.py` to accept optional `original_parsed_sets` on `CommitSetsRequest`, resolve exercises by `id OR slug` (updating `ex_id = ex_obj.id` when auto-seeding), enforce exact idempotency via `StrengthSet.submission_key == payload.idempotency_key` with `idempotency_key = f"{payload.idempotency_key}:{seq}"` for every row, persist distinct `parsed_json` (`original_parsed_sets`) vs `final_confirmed_json` in `VoiceTranscriptionLog`, add `GET /api/v1/gym/sessions/{session_id}/sets`, use UUID suffix in session `external_id`, and switch to `src/core/deps.py`
- [X] T042 [P] [US3] Refactor Gym Mode UI into CSP-compliant `src/static/gym.html` and `src/static/js/gym.js` using `common.css`/`common.js` to render & commit ALL multi-clause `parsed_sets`, clear `exercise_id` when the exercise name field is edited, compute genuine `was_edited` + pass `original_parsed_sets`, restore today's sets on page load via `GET /api/v1/gym/sessions/{id}/sets`, convert `kg` → `lbs` and include `added_weight` in live volume ticker, use `safeUUID()` for non-HTTPS LAN access, implement `localStorage` offline queue (`coach3_gym_offline_queue_v1`) with pending-sync badge and `online` auto-flush, escape all dynamic text, and enable mobile pinch-to-zoom
- [X] T043 [P] [US3] Refactor Settings UI into CSP-compliant `src/static/config.html` and `src/static/js/config.js` using `common.css`/`common.js` to render `masked_client_id` strictly as `<input placeholder>` (never `.value`), support secret-only rotation, show clear re-entry notice when `decryption_error=true`, load existing AI providers on init and call `POST /api/v1/coaching/providers/{id}/activate` after save, use `safeCopy()` fallback, escape all diagnostic strings, and enable mobile pinch-to-zoom

### Tests for User Story 3

- [X] T044 [P] [US3] Expand `tests/unit/test_gym_parser.py` to test preposition-less weight parsing (`"bench press 225 lbs 3x5"`, `"225lb squat 5x5"`), metric `default_unit="kg"` preservation, unrecognized gibberish returning `is_ambiguous=True` with empty `parsed_sets`, and multi-clause parsing
- [X] T045 [P] [US3] Expand `tests/unit/test_config_service.py` to test masked-bullet rejection, secret-only rotation preserving Client ID, and graceful `InvalidToken` returning `decryption_error=True`
- [X] T046 [US3] Expand `tests/integration/test_gym_api.py` to test committing Bench Press *after* `SeedService.seed_sample_workouts()`, committing two 1-set exercises in one request, prefix-similar idempotency keys (`key_1` vs `key_10`), edited exercise name resolution, distinct `parsed_json` vs `final_confirmed_json` in `VoiceTranscriptionLog`, and `GET /api/v1/gym/sessions/{session_id}/sets`

**Checkpoint**: User Story 3 (Settings credential safety & resilient Gym Mode) is complete and independently verifiable.

---

## Phase 6: User Story 4 - Consistent Analytics, Honest Telemetry, and Scalable Performance (Priority: P2)

**Goal**: Eliminate OOM list/recalc queries, unify Epley 1RM across Dashboard & PRs, fix athlete local-timezone weekly bucketing and cross-year sorting, remove silently fabricated HR pace, harden request validation bounds, fix AI Coach UI bugs, and add AI concurrency locks & schedule invariant validation.

**Independent Test**: Load Dashboard workouts list with dense telemetry (verify zero HR sample hydration and working window filters), update Heart Rate Profile (verify batched recalc + `422` on invalid zones + `resting_hr=28` accepted), verify Sunday-evening Pacific workout lands in Sunday week, verify identical Epley 1RM across cards, verify concurrent AI calls return `409`, and verify invalid LLM schedules are rejected.

### Implementation for User Story 4

- [X] T047 [P] [US4] Create canonical `src/services/metrics.py` (`calculate_epley_1rm` capped at `1 <= reps <= 10`, `calculate_estimated_5rm`, `KG_TO_LBS`, `KM_TO_MILES`) and refactor both `src/services/pr_detector.py` and `src/services/analytics_service.py` to use it exclusively
- [X] T048 [P] [US4] Harden validation schemas in `src/schemas/profile.py` (add `@model_validator` enforcing `resting_hr >= 25`, `resting_hr < max_hr`, positive monotonically ordered zones; add `AthletePreferences` validating IANA `timezone` via `ZoneInfo`), `src/schemas/coaching.py` (add `temperature: 0.0..2.0`, `max_tokens: 64..32768`, `target_zone2_pct: 0.0..100.0`, `max_weekly_volume_ramp_pct: 0.0..100.0`, `max_rpe_threshold: 1.0..10.0`, `min_rest_days_per_week: 0..7`, `Literal` enums for `primary_modality` and `LLMWorkoutItem.discipline`, and `ScheduledWorkoutUpdateRequest`), and `src/schemas/workout.py` (replace mutable `= []` defaults with `Field(default_factory=list)`, add `WorkoutUpdateRequest`, cap `GPXUploadRequest.gpx_xml` at `10_000_000` chars)
- [X] T049 [US4] Remediate `src/services/analytics_service.py` and `src/api/analytics.py` to resolve date windows and weekly Monday buckets in the athlete's configured IANA `timezone`, sort `get_cardio_metrics` weekly buckets chronologically by Monday `date`, pair each muscle group's `estimated_1rm_lbs` with its displayed top exercise, and remove silent HR-derived fake pace (`hr_smooth_map`) while exposing explicit `pace_source` metadata on `WorkoutDetailTelemetry`
- [X] T050 [US4] Remediate `src/api/workouts.py` to eliminate `selectinload(WorkoutSession.heart_rate_samples)` in `list_workouts` using SQL `EXISTS`/`COUNT` subqueries, exclude warmup sets from working-set labels, filter strictly by `user_id`, `status == "active"`, and `window`/`start_date`/`end_date` (evaluated in athlete timezone), add `offset` + `X-Total-Count` pagination header, and switch to `src/core/deps.py`
- [X] T051 [US4] Remediate `src/api/profile.py` to process historical HR zone recalculation in bounded batches of 25 workouts (preventing OOM on multi-year histories) and add `GET /api/v1/profile/preferences` and `PUT /api/v1/profile/preferences` for athlete IANA timezone
- [X] T052 [US4] Remediate `src/services/coaching_service.py`, `src/services/philosophy_service.py`, and `src/api/coaching.py` to enforce per-user in-flight concurrency locks returning `409 Conflict` on overlapping `/analyze` or `/plan` calls, validate generated `LLMScheduleOutput` invariants (valid `day_offset` within `0..horizon_days-1`, unique dates, `0 <= planned_duration_min <= 480`, minimum rest days honored), calculate baseline weekly volume from actual active weeks in athlete timezone, and enforce bounded `limit: int = Query(default=..., ge=1, le=100)` in `src/api/coaching.py` and `src/api/integrations.py`
- [X] T053 [P] [US4] Refactor Dashboard UI into CSP-compliant `src/static/dashboard.html` and `src/static/js/dashboard.js` using `common.css`/`common.js` to pass preset window filters to `/api/v1/workouts`, escape all rendered workout titles/PRs/metrics/errors via `escapeHtml()`, clear `cachedDetailData` on filter changes, label pace source honestly, and enable mobile pinch-to-zoom
- [X] T054 [P] [US4] Refactor AI Coach UI into CSP-compliant `src/static/coach.html` and `src/static/js/coach.js` using `common.css`/`common.js` to fix missing `#critique-result` with a dedicated `#critique-error` banner, render markdown safely via `formatMarkdown()`, escape all scheduled workout fields, check `res.ok` before provider activation, preserve `description` and `primary_modality` on philosophy save, pass explicit `event` to `switchTab()`, disable buttons while AI calls are in flight, unify AI provider config with `/config`, and enable mobile pinch-to-zoom

### Tests for User Story 4

- [X] T055 [P] [US4] Expand `tests/unit/test_analytics_service.py` and `tests/unit/test_pr_detector.py` to assert identical Epley 1RM between Dashboard & PRs, top-lift 1RM attribution, cross-year chronological week sorting, `America/Los_Angeles` Sunday-evening local week bucketing, and absence of fabricated HR pace
- [X] T056 [P] [US4] Expand `tests/unit/test_coaching_service.py` to test concurrent in-flight lock rejection, schedule invariant validation (invalid day offsets, duplicate dates, >480m duration, missing rest days), and active-weeks baseline calculation for new athletes
- [X] T057 [P] [US4] Expand `tests/integration/test_dashboard_api.py` and `tests/integration/test_api_endpoints.py` to test HR profile `422` validation (inverted bounds & overlapping zones), `resting_hr=28` acceptance, batched HR zone recalculation, workouts list window/user/status/offset/warmup-exclusion behavior, and bounded `limit`/GPX validation

**Checkpoint**: User Story 4 (scalable, consistent, timezone-accurate analytics & hardened AI Coach) is complete and independently verifiable.

---

## Phase 7: User Story 5 - Training History Export, Daily Editing Controls, and Diagnostics (Priority: P3)

**Goal**: Deliver one-click lossless ZIP export (`backup.json` + `workouts.csv` + `strength_sets.csv`), everyday workout/set/plan editing controls, Settings System Health & Sync Diagnostics card, unified transaction boundaries across all routers, and real PostgreSQL migration round-trip verification.

**Independent Test**: Download and verify ZIP export (lossless JSON + CSV summaries, zero demo records or secrets); edit workout notes, delete a strength set, toggle planned workout completion, paginate workouts; inspect Settings Diagnostics card; run real PostgreSQL `upgrade head -> downgrade base -> upgrade head` tests.

### Implementation for User Story 5

- [X] T058 [P] [US5] Implement `ExportService` in `src/services/export_service.py` and `GET /api/v1/export` in `src/api/export.py` returning a downloadable `application/zip` archive containing lossless `backup.json` (workouts, HR samples, GPS points, splits, strength sets, exercises, HR profile, athlete timezone, philosophies, critiques, training plans; excluding encrypted credentials and excluding `is_demo=True` by default), `workouts.csv`, and `strength_sets.csv`
- [X] T059 [P] [US5] Implement `GET /api/v1/system/diagnostics` in `src/api/diagnostics.py` (database reachability, Alembic revision, scheduler status & next sync time, per-provider decryption/sync health, `has_recent_sync_failures` boolean, and latest 10 `SyncAuditLog` rows) and register `export` and `diagnostics` routers in `src/api/router.py`
- [X] T060 [P] [US5] Implement everyday CRUD endpoints: `PATCH /api/v1/workouts/{workout_id}` (edit `title`/`user_notes`) in `src/api/workouts.py`, `DELETE /api/v1/gym/sets/{set_id}` (delete strength set) in `src/api/gym.py`, and `PATCH /api/v1/coaching/scheduled-workouts/{scheduled_workout_id}` (toggle `is_completed`) in `src/api/coaching.py`
- [X] T061 [US5] Wire new UI controls into `src/static/config.html` + `src/static/js/config.js` (Athlete Timezone selector, one-click "Export Training History (.zip)" button, and **System Health & Sync Diagnostics** panel with failure warning badge), `src/static/js/dashboard.js` (inline workout title/notes editor + "Load More" pagination), `src/static/js/gym.js` (delete/undo set button), and `src/static/js/coach.js` (scheduled workout completion toggle)
- [X] T062 [P] [US5] Normalize single-owner transaction boundaries and remove all remaining duplicate `get_or_create_default_user` helpers across `src/api/admin.py`, `src/api/analytics.py`, `src/api/coaching.py`, `src/api/config.py`, `src/api/gym.py`, `src/api/integrations.py`, `src/api/profile.py`, and `src/api/workouts.py` (relying on `src/core/deps.py` and `get_db()` commit/rollback)

### Tests for User Story 5

- [X] T063 [P] [US5] Add integration tests in `tests/integration/test_export_and_crud.py` verifying ZIP archive contents (`backup.json`, `workouts.csv`, `strength_sets.csv`, zero encrypted secrets, demo isolation), `PATCH /api/v1/workouts/{id}`, `DELETE /api/v1/gym/sets/{id}`, `PATCH /api/v1/coaching/scheduled-workouts/{id}`, `GET/PUT /api/v1/profile/preferences`, `GET /api/v1/system/diagnostics`, and `GET /api/v1/workouts?offset=...`
- [X] T064 [P] [US5] Update `tests/integration/test_static_routes.py` to verify `/login`, shared `/static/css/common.css` & `/static/js/*.js` assets, browser security headers/CSP, and absence of `user-scalable=no` across all HTML shells
- [X] T065 [US5] Add real PostgreSQL migration & constraint test suite in `tests/integration/test_postgres_migrations.py` (gated by `TEST_DATABASE_URL`, executing `alembic upgrade head` → `downgrade base` → `upgrade head`, verifying partial unique active indexes on `llm_provider_configs` and `coaching_philosophies`, HR zone check constraints, and `ON CONFLICT` workout upserts)

**Checkpoint**: All 5 user stories are complete, unified, and independently verified.

---

## Phase 8: Polish, Static Analysis & Final Verification

**Purpose**: Documentation alignment, zero-warning static analysis & typing pass, and end-to-end quickstart verification.

- [X] T066 [P] Update `README.md` to document required `ENCRYPTION_KEY`, `COACH3_PASSPHRASE`, `ALLOWED_ORIGINS`, `TRUST_PROXY_HEADERS`, automatic container migrations, ZIP export, System Diagnostics, and PostgreSQL/ruff/mypy verification commands
- [X] T067 Run `.venv/bin/ruff check src tests` and resolve all lint and security (`S`) findings across `src/` and `tests/`
- [X] T068 Run `.venv/bin/mypy src` and resolve all static type errors across `src/`
- [X] T069 Run full test suite `.venv/bin/pytest -W default -v` (confirming zero failures and zero deprecation warnings) and execute `tests/integration/test_postgres_migrations.py` against PostgreSQL
- [X] T070 Execute end-to-end validation scenarios from `specs/007-remediation/quickstart.md` (including Docker Python 3.12 container build/boot verification)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS** all user stories (`US1`–`US5`).
- **Phase 3 (`US1` — P1 MVP)**, **Phase 4 (`US2` — P1)**, **Phase 5 (`US3` — P1)**: All depend on Phase 2; once Phase 2 is complete, `US1`, `US2`, and `US3` can proceed in parallel or strictly sequentially (`US1 → US2 → US3`).
- **Phase 6 (`US4` — P2)**: Depends on Phase 2 (and benefits from `US3`'s shared frontend shell pattern in `T017`).
- **Phase 7 (`US5` — P3)**: Depends on Phase 2 (`T058`–`T060`, `T062` can run after Phase 2; `T061` builds onto the refactored frontend JS files from `US3` & `US4`).
- **Phase 8 (Polish)**: Depends on all desired user stories (`US1`–`US5`) being complete.

### Parallel Opportunities

- **Phase 2**: `T006`, `T007`, `T008`, `T009`, `T010`, `T011`, `T012`, `T013`, `T014` touch distinct core/model files and can run in parallel before `T016` (migration `006`).
- **Phase 3 (`US1`)**: `T018` (`auth.py`), `T019` (`api/auth.py`), `T020` (`login.html/js`), `T021` (`privacy.py`), `T022` (`llm_client.py`), `T025` (`Docker*`) can all run in parallel before `T024` (`main.py`).
- **Phase 4 (`US2`)**: `T029` (`base.py`), `T030` (`polar.py`), `T031` (`concept2.py`) can run in parallel before `T033` (`sync_service.py`).
- **Phase 5 (`US3`)**: `T038` (`config_service`), `T039` (`exercise_catalog`/seeders), `T040` (`gym_parser`), `T042` (`gym.js`), `T043` (`config.js`) can run in parallel.
- **Phase 6 (`US4`)**: `T047` (`metrics.py`), `T048` (schemas), `T053` (`dashboard.js`), `T054` (`coach.js`) can run in parallel.
- **Phase 7 (`US5`)**: `T058` (`export_service`), `T059` (`diagnostics.py`), `T060` (CRUD endpoints), `T062` (deps cleanup) can run in parallel before `T061` (UI wiring).

---

## Parallel Example: User Story 1

```bash
# Run core US1 security modules concurrently (distinct files):
Task T018: "Implement scrypt auth & rate limiter in src/core/auth.py"
Task T021: "Extend PrivacyScrubberService in src/core/privacy.py & src/services/coaching_service.py"
Task T022: "Harden Gemini header key & SSRF guard in src/services/llm_client.py"
Task T025: "Create docker-entrypoint.sh and harden Dockerfile & docker-compose.yml"
```

---

## Implementation Strategy

### MVP First (P0 Security + Lossless Sync + Gym/Settings Fixes)

1. Complete **Phase 1 (Setup)** + **Phase 2 (Foundational)** (`T001`–`T017`).
2. Complete **Phase 3 (`US1`)** → Hardened boot, auth, CORS, CSP, OAuth CSRF, SSRF, PII scrubbing (`T018`–`T028`).
3. Complete **Phase 4 (`US2`)** → Lossless Polar/Concept2 sync & accurate telemetry (`T029`–`T037`).
4. Complete **Phase 5 (`US3`)** → Safe Settings credentials & resilient Gym Mode (`T038`–`T046`).
5. **STOP & VALIDATE P0/P1 Checkpoint**: Run full pytest suite + verify all P0 security & data-loss issues are closed.
6. Complete **Phase 6 (`US4`)** → Scalable analytics, timezones, validation, AI Coach locks (`T047`–`T057`).
7. Complete **Phase 7 (`US5`)** → ZIP export, everyday CRUD, Settings Diagnostics, Postgres migration tests (`T058`–`T065`).
8. Complete **Phase 8 (Polish)** → `ruff`, `mypy`, zero-warning `pytest`, quickstart & Docker verification (`T066`–`T070`).
