# Phase 0 Research & Architectural Decisions: Coach3 Remediation (`007-remediation`)

**Date**: 2026-11-24  
**Feature**: [spec.md](spec.md)

This document resolves all architectural, security, data-modeling, and operational decisions required to remediate P0, P1, and P2 audit findings and systems-engineering additions without introducing unnecessary external infrastructure.

---

## R1. Single-User Passphrase Authentication, Session Cookies & Brute-Force Protection (`FR-005`, `FR-041`)

- **Decision**:
  - Implement a built-in single-user passphrase authentication layer backed by an HMAC-SHA256 signed, expiring session cookie (`coach3_session`, `HttpOnly=True`, `SameSite="lax"`, `Secure=True` when the request scheme is `https`, 30-day TTL).
  - Derive the passphrase hash using Python stdlib `hashlib.scrypt` (memory-hard KDF, zero new dependencies) and compare using `hmac.compare_digest`.
  - Support configuring the passphrase via `COACH3_PASSPHRASE` (hashed at startup) or `COACH3_PASSPHRASE_HASH`, with an explicit `AUTH_DISABLED_LOCALHOST=true` escape hatch that **only** takes effect when `ENVIRONMENT == "development"` and the request originates from loopback (`127.0.0.1` / `::1` / `testclient`), and is automatically refused if the server binds publicly or `ENVIRONMENT != "development"`.
  - Serve a clean `/login` page (plus `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/status`). Protect all `/api/v1/*` routes (except `/api/v1/auth/login`, `/api/v1/auth/status`, and OAuth provider callbacks which validate one-time `state` nonces) and redirect unauthenticated HTML page requests to `/login`.
  - Enforce in-memory per-IP sliding-window brute-force throttling on `POST /api/v1/auth/login` (e.g., max 5 failed attempts per 5 minutes, escalating lockout backoff up to 15 minutes, returning `429 Too Many Requests` with `Retry-After`).
- **Rationale**:
  - Zero external auth service needed for a self-hosted homelab; stdlib `scrypt` + signed cookie works seamlessly on desktop and iPhone Safari without breaking offline-friendly web ergonomics.
  - Requiring auth by default whenever accessed beyond localhost protects LAN/homelab biometric and GPS data without slowing down local pytest runs or localhost dev.
- **Alternatives Considered**:
  - *Full multi-user JWT + database user registration*: Rejected as unnecessary complexity; Coach3 is explicitly single-athlete self-hosted.
  - *HTTP Basic Auth*: Rejected due to poor mobile Safari UX, inability to cleanly sign out, and lack of CSRF/cookie control.
  - *External reverse-proxy auth only*: Rejected because users running directly on a home LAN without Authelia/Tailscale would remain exposed.

---

## R2. Encryption Key Enforcement, Graceful `InvalidToken` Degradation & OAuth2 CSRF (`FR-003`, `FR-006`, `FR-039`)

- **Decision**:
  - Remove the hardcoded default `ENCRYPTION_KEY` from `src/core/config.py`. Require `ENCRYPTION_KEY` to be explicitly provided (validated as a valid 32-byte url-safe base64 Fernet key during startup) whenever `ENVIRONMENT != "test"`. In `test` mode (or pytest), generate a transient ephemeral key if unset so unit tests stay self-contained without shipping a hardcoded production secret.
  - Wrap all `decrypt_token()` call sites in `ConfigService`, `LLMProviderConfig`, `integrations.py`, and `sync_service.py` to catch `cryptography.fernet.InvalidToken`, logging a structured warning and returning a `decryption_error=True` state (rather than crashing with HTTP 500) so `/config` stays loadable and guides the athlete to re-enter affected credentials.
  - Store single-use OAuth2 `state` nonces in a dedicated `oauth_states` table (`state`, `provider`, `user_id`, `expires_at` = +10 min) generated in `GET /api/v1/integrations/{provider}/auth-url` and atomically validated + consumed (deleted) in `GET /api/v1/integrations/{provider}/callback`. Expired states are pruned on create/verify.
- **Rationale**:
  - Database-backed single-use OAuth state nonces prevent both OAuth CSRF and replay attacks, work reliably behind reverse proxies and across OAuth redirects (unlike strict cookies that some mobile browsers drop on cross-site redirects), and require zero Redis/cache infrastructure.
- **Alternatives Considered**:
  - *In-memory dict for OAuth states*: Rejected because it breaks on container restarts or multi-worker deployments.
  - *Hard-crashing `/config` on key mismatch*: Rejected because it locks the owner out of re-entering credentials in the UI.

---

## R3. Defense-in-Depth Web Security, Reverse Proxy Awareness & Privacy Scrubbing (`FR-004`, `FR-007`–`FR-010`, `FR-040`, `FR-041`)

- **Decision**:
  - **CORS**: Replace `allow_origins=["*"]` with configurable `ALLOWED_ORIGINS` (defaulting to empty list / same-origin only; e.g. `http://localhost:8000`). Never allow wildcard `*` with `allow_credentials=True`.
  - **Security Headers Middleware**: Apply on every response:
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `Referrer-Policy: no-referrer` (prevents leaking OAuth `?code=...` in `Referer` headers)
    - `Permissions-Policy: geolocation=(), camera=(), microphone=(self)` (allows Gym Mode microphone on self-origin only)
    - `Content-Security-Policy`: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` — moving all page JS out of inline `<script>` tags into external `/static/js/*.js` files eliminates inline script execution completely!
  - **Reverse Proxy Awareness**: Support optional `TRUST_PROXY_HEADERS=true` and `FORWARDED_ALLOW_IPS` passed to `uvicorn` (`--proxy-headers`) plus a middleware/helper that resolves external origin cleanly for OAuth redirect URIs and cookie `Secure` flag.
  - **Gemini API Key in Header**: Change `GeminiClient` to send `headers={"x-goog-api-key": self.api_key}` with URL `f"{self.base_url}/{self.model_name}:generateContent"` (zero `?key=` in URLs), and sanitize any exception messages before logging or returning to clients.
  - **SSRF Guard for `LlamaCppClient`**: Validate `endpoint_url` scheme (`http`/`https` only), resolve hostname IPs, block link-local / cloud metadata ranges (`169.254.0.0/16`, `fe80::/10`, `0.0.0.0/8`), and optionally enforce `ALLOWED_LLM_HOSTS` allowlist. Allow `localhost`/`127.0.0.1` and RFC1918 homelab LAN IPs (since homelab `llama.cpp` runs locally or on LAN) while blocking cloud metadata and non-HTTP schemes (`file://`, `gopher://`).
  - **XSS Elimination**: Escape all untrusted text via a shared `escapeHtml()` utility in `/static/js/common.js`, rewrite `formatMarkdown()` to HTML-escape *before* markdown transforms (and validate any generated structure), and prefer `textContent` / DOM creation over `innerHTML`.
  - **Complete PII Scrubbing**: Run `PrivacyScrubberService.scrub_text()` on `philosophy.custom_context_notes`, `philosophy.name`, `target_goal`, `title`, and `user_notes` before constructing *both* system and user prompts. Extend scrubber patterns to redact emails, IPv4/IPv6 addresses, phone numbers, raw decimal GPS coordinate pairs (e.g., `37.7749, -122.4194`), and optional `SCRUB_TERMS` env list (e.g., athlete's own name/city).
- **Rationale**:
  - Extracting inline `<script>` blocks to `/static/js/*.js` simultaneously enables a strict `script-src 'self'` CSP (neutralizing XSS even if an escaping bug were ever introduced) and cleanly deduplicates frontend code (`FR-034`).
- **Alternatives Considered**:
  - *Keeping `'unsafe-inline'` in `script-src`*: Rejected because it weakens CSP to near-zero protection against XSS.

---

## R4. Lossless Sync, Error Propagation, Pagination, Backoff & Scheduler Resilience (`FR-011`–`FR-017`, `FR-039`, `FR-042`)

- **Decision**:
  - **Deferred Polar Transaction Commit**: Return an opaque `pending_commit_token` (e.g., `{"user_id": ..., "transaction_id": ...}`) inside `SyncBatchResult`. Add `commit_batch(access_token, commit_token)` on `BaseIngestionAdapter` (implemented by `PolarAdapter` to send `PUT {tx_url}/{transaction_id}`, no-op on `Concept2Adapter`). `sync_service.run_sync_for_account` calls `await adapter.commit_batch(...)` **only after** `await db.commit()` succeeds!
  - **Error Propagation & 401-Only Token Refresh**: Remove `except httpx.HTTPError: return empty` from both `PolarAdapter` and `Concept2Adapter`. Introduce a shared HTTP helper with bounded exponential backoff + jitter (max 3 attempts on `429`/`502`/`503`/`504`/network timeouts, honoring `Retry-After` up to 30s) and explicit per-request timeouts (15s auth/verify, 30s batch fetch, 60s LLM). In `sync_service`, catch specifically `httpx.HTTPStatusError` with `status_code == 401` to trigger token refresh and a single retry.
  - **Full Pagination Loop**: In `sync_service`, loop `while True:` up to a safety cap (e.g., 50 pages per sync run) calling `adapter.fetch_workouts_batch(access_token, cursor=cursor, since=since)`. Persist each page cleanly, update `account.sync_cursor = batch.next_cursor`, and only set `account.last_sync_at = now` and clear `account.sync_cursor = None` when `not batch.has_more`.
  - **Clean Error Rollback**: If any error occurs inside `run_sync_for_account`, execute `await db.rollback()`, open/persist a clean `SyncAuditLog` row with `status="failed"` and sanitized `error_message`, and commit only that audit log.
  - **Soft-Sync Zone Preservation & Bulk Upsert**: In `ingest_workout()`, only overwrite `zone1_duration_sec`..`zone5_duration_sec` when `normalized.heart_rate_samples` is non-empty (or when creating a new session). Use PostgreSQL `INSERT ... ON CONFLICT (provider, external_id) DO UPDATE` (with fallback select-then-upsert on SQLite) and bulk `session.execute(insert(HeartRateSample), rows)` / `insert(GPSRoutePoint)` for dense telemetry.
  - **Scheduler Resilience**:
    - Isolate each account in its own `async with async_session_factory() as db:` block inside `scheduled_sync_job()`.
    - Acquire a PostgreSQL session advisory lock (`pg_try_advisory_lock`) around scheduled sync runs so multiple uvicorn workers never double-sync simultaneously.
    - On startup (`lifespan`), mark any orphaned `SyncAuditLog` rows with `status == 'running'` as `status = 'failed'` (`error_message = 'Interrupted by server restart'`, `completed_at = now`).
    - On shutdown (`lifespan`), stop scheduler with bounded graceful draining (`wait=True` / awaiting active sync task with timeout) and call `await engine.dispose()`.
- **Rationale**:
  - Guarantees at-least-once delivery from Polar without losing workouts on DB errors, zero skipped Concept2 history pages, clean audit trails under all failure modes, and bounded shutdown behavior.
- **Alternatives Considered**:
  - *Celery/Redis task queue*: Rejected as heavy operational overhead violating the Constitution's minimal-maintenance single-box self-hosted Deployment Model.

---

## R5. Endurance Telemetry Math, Analytics Consistency, Timezones & Query Performance (`FR-014`–`FR-016`, `FR-025`–`FR-029`, `FR-038`)

- **Decision**:
  - **Concept2 Exact Units**: Concept2 Logbook API returns `time` and `rest_time` in tenths of a second (`1/10s`) consistently for work summaries, intervals, and rests; divide integer tenths unconditionally by `10.0` (only preserving explicit float-seconds fixtures via a clean helper or updating test fixtures where tenths are standard, ensuring `600` tenths = `60.0s` and `900` tenths = `90.0s`, NEVER 10x inflated!). For `erg_bike`, Concept2 `pace` is tenths of a second per 1000m (not 500m), so store `raw_pace / 10.0` into `avg_pace_sec_per_km` and `avg_pace_sec_per_km / 2.0` (or `None`) into `avg_split_sec_per_500m`.
  - **Polar Sport Mapping & ID Validation**: Reject records with missing/empty `id` (`ValueError` skipped with diagnostic warning). Map Polar `sport` / `detailed-sport-info` strings (e.g., `RUNNING` / `TRAIL_RUNNING` → `outdoor_run`, `ROWING` / `INDOOR_ROWING` → `indoor_row`, `CYCLING` / `INDOOR_CYCLING` → `erg_bike`, `STRENGTH_TRAINING` → `strength`, with sensible fallback + logged warning for unmapped sports).
  - **Unified 1RM Formula**: Centralize `calculate_epley_1rm(weight, reps)` (`w * (1 + r / 30)` capped at `1 <= reps <= 10`, returning `None` for `reps > 10`) in a shared `src/services/metrics.py` helper used by both `AnalyticsService` and `PRDetectorService`. In `get_macro_dashboard_volume()`, track the muscle group's best set by top weight and compute `estimated_1rm_lbs` from that same lift (or track best 1RM exercise explicitly so weight and 1RM are never mismatched across two different exercises).
  - **Athlete IANA Timezone Bucketing**: Add `timezone: str = "UTC"` on `users` (validated via `zoneinfo.ZoneInfo`, editable on `/config` under Profile Settings). Convert `WorkoutSession.start_time_utc` to `ZoneInfo(user.timezone)` before deriving local date, Monday week bucket, and custom `start_date`/`end_date` UTC bounds. Sort weekly cardio buckets strictly by Monday `date` key in *both* `get_macro_dashboard_volume` and `get_cardio_metrics`.
  - **Honest Pace Representation**: Remove silent HR-derived fake pace fabrication (`hr_smooth_map`) from `get_workout_detail_telemetry()` `pace_sec` (only plot real Polar speed samples, GPS Haversine pace, Concept2 stroke pace, or split pace; return `pace_source` metadata so the UI transparently labels measured vs split-averaged pace).
  - **OOM & Query Elimination**:
    - `GET /api/v1/workouts`: Remove `selectinload(WorkoutSession.heart_rate_samples)`. Use SQL `EXISTS` subquery for `has_hr_samples`, `COUNT` subquery for interval splits (`split_type IN ('interval', 'work')`), and `COUNT` subquery for non-warmup working sets (`is_warmup IS FALSE`). Filter strictly by `user_id == user.id`, `status == "active"`, and date window (`window` preset or `start_date`/`end_date`) with `limit` + `offset`.
    - `PUT /api/v1/profile/heart-rate`: Process workouts in bounded batches (e.g., 25 workouts per batch, streaming/fetching HR samples per batch and flushing) rather than loading every HR sample in history in a single query.
    - `StrengthExercise.sets`: Change `lazy="selectin"` to `lazy="select"` (or `"raise"`). Change `WorkoutSession.strength_sets` and `WorkoutSession.voice_logs` from `lazy="selectin"` to `lazy="select"` (using explicit `selectinload` only where actually needed).
- **Rationale**:
  - Eliminates hundreds of thousands of unnecessary ORM allocations on dashboard load, fixes the Sunday-evening timezone off-by-one bug, and makes every number across the UI mathematically consistent and truthful.

---

## R6. Settings Credential Safety, Unified AI Config, Gym Mode Fixes & Offline Buffering (`FR-018`–`FR-024`)

- **Decision**:
  - **Masked Client ID Fix**: Render `masked_client_id` in `<input placeholder="...">` (never `.value`). Allow `POST /api/v1/config/integrations/{provider}` to accept an optional `client_id` when updating only `client_secret` on an already-configured provider, and reject any submitted value containing mask bullets (`•`).
  - **Unified AI Provider Config**: Make `/config` the canonical configuration surface (loading existing providers on init, calling `/providers/{id}/activate` after save, and testing the active provider) and make `/coach` link cleanly to `/config#ai-providers` (or share the exact same `/static/js/ai_providers.js` controller so both stay 100% consistent and check `res.ok`).
  - **Deterministic Exercise Catalog**: Standardize on deterministic `uuid5(NAMESPACE_DNS, f"coach3.exercise.{slug}")` in `ExerciseCatalogService`, `seed_exercises.py`, AND `SeedService.ensure_default_exercises()`. Call `await catalog_service.load_from_db(session)` in app `lifespan` (and on-demand reload), and in `gym.py` resolve exercises by `id` OR `slug` before inserting, updating `ex_id = ex_obj.id` before creating `StrengthSet`.
  - **Exact Gym Idempotency**: Add a dedicated `submission_key` (`String(100)`, indexed) on `strength_sets` storing the client's `idempotency_key` verbatim, and assign each individual row `idempotency_key = f"{payload.idempotency_key}:{seq_idx}"`. Look up retries via exact equality `StrengthSet.submission_key == payload.idempotency_key` (zero `LIKE` wildcard/prefix bugs, zero multi-candidate collisions).
  - **GymParser Fixes**:
    - Support bare `<weight> <unit>` without leading prepositions (`"bench press 225 lbs 3x5"`, `"225lb squat 5x5"`).
    - Honor `default_unit` whenever unit is omitted (`"bench press at 100"` with `default_unit="kg"` → `"kg"`).
    - Stop forcing low-score alternatives when `best_score < min_score` (return `None` candidate + `is_ambiguous=True` + `alternative_exercises`).
    - Remove dead `weight_match` variable.
  - **Gym UI & Offline Buffer**:
    - Render editable cards for **all** items in `data.parsed_sets` (multi-clause support).
    - Clear `exercise_id` whenever the user edits the exercise name input so the backend resolves the new exercise name.
    - Send `original_parsed_sets` alongside final `sets`, compute `was_edited` dynamically, and store both separately in `VoiceTranscriptionLog`.
    - Fetch existing sets for the active session on page load (`GET /api/v1/gym/sessions/{id}/sets`).
    - Convert `kg` → `lbs` and include `added_weight` in the live volume ticker.
    - Provide a non-HTTPS-safe UUIDv4 generator (`crypto.getRandomValues` / `Math.random` fallback) and clipboard fallback so LAN HTTP iPhone usage never crashes.
    - Store failed/offline commit payloads (with their client-generated `idempotency_key`) in `localStorage` (`coach3_gym_offline_queue`), display a pending-sync badge, and automatically flush the queue on `window.online` and page load.
- **Rationale**:
  - Directly satisfies Constitution Principle III (multimodal ergonomics, fault tolerance, human-verifiable staging) and Technical Constraints (offline buffering on iPhone).

---

## R7. AI Coaching Concurrency Guard, Plan Invariants & Structured Observability (`FR-030`, `FR-031`, `FR-043`, `FR-044`)

- **Decision**:
  - **In-Flight AI Deduplication**: Maintain a per-user `asyncio.Lock` (or in-flight tracking set keyed by `(user_id, operation)`) in `CoachingService` so a second concurrent `/analyze` or `/plan` request for the same athlete while one is already running immediately returns `409 Conflict` ("An AI coaching request is already in progress"), paired with disabled buttons in the UI.
  - **Plan Sanity Validation**: Validate parsed `LLMScheduleOutput` before persisting:
    - `1 <= len(workouts) <= horizon_days`
    - All `day_offset` values in `0..horizon_days - 1` with no duplicate dates
    - All `discipline` values in `{'outdoor_run', 'indoor_row', 'erg_bike', 'strength', 'rest'}`
    - `0 <= planned_duration_min <= 480` (and `0` allowed for `rest`)
    - Count of `rest` days >= floor proportional to `philosophy.min_rest_days_per_week` (or explicitly flagged/rejected if violated).
  - **Coach UI & Baseline Fixes**: Fix `#critique-result` → dedicated `#critique-error` banner; check `res.ok` before activating provider; preserve `description` & `primary_modality` on philosophy save; compute baseline weekly volume using `max(1.0, active_weeks)` in the athlete's configured timezone.
  - **Structured Secret-Redacted Logging & Diagnostics**:
    - Configure JSON/structured logging in `src/core/logging.py` with a `contextvars`-backed `request_id` (propagated via `X-Request-ID` header) and a `logging.Filter` that automatically redacts tokens (`Bearer ...`, `key=...`, `AIza...`, `api_key`, `client_secret`, `passphrase`).
    - Add `GET /api/v1/system/diagnostics` returning DB reachability, Alembic schema revision, scheduler running state + next sync time, integration encryption health, and the last 10 `SyncAuditLog` rows—rendered in a dedicated **System Health & Sync Diagnostics** card on `/config` with a visible warning badge whenever the latest sync for any connected provider failed.
- **Rationale**:
  - Eliminates silent multi-week sync failures and GPU/API double-billing while keeping diagnostics completely self-hosted.

---

## R8. Lossless Export Archive, Everyday CRUD, Unified Frontend & `personal_records` Reconciliation (`FR-032`–`FR-036`)

- **Decision**:
  - **Full ZIP Export (`GET /api/v1/export`)**: Stream/build an in-memory ZIP archive (`coach3-export-YYYYMMDD-HHMMSS.zip`) containing:
    - `backup.json`: Lossless structured snapshot of all authentic (`is_demo=False`) workouts, HR samples, GPS points, splits, strength sets, exercise mappings, HR profile, athlete timezone, coaching philosophies, critiques, and training plans (excluding encrypted third-party secrets/tokens for safety!).
    - `workouts.csv`: Clean summary table of all authentic workouts.
    - `strength_sets.csv`: Clean table of all authentic strength sets with canonical exercise names, weights, units, RPE, and warmup flags.
    - Exposed via a one-click **"Export Training History (.zip)"** button on `/config`.
  - **Everyday CRUD Endpoints**:
    - `PATCH /api/v1/workouts/{workout_id}`: Update `title` and/or `user_notes` (inline edit button in Dashboard drawer).
    - `DELETE /api/v1/gym/sets/{set_id}`: Undo/delete a mistakenly logged strength set (undo/delete icon in Gym Mode feed).
    - `PATCH /api/v1/coaching/scheduled-workouts/{scheduled_workout_id}`: Toggle `is_completed` (checkbox on AI Coach plan calendar).
    - `GET /api/v1/workouts`: Add `offset` + `total_count` header/pagination support ("Load more" in Dashboard table).
  - **Reconcile Dead `personal_records` Table**: Drop the unused `personal_records` table and model in migration `006` (reversible in `downgrade()`). Keep `PRDetectorService` computing deterministic PRs live from `strength_sets` and `workout_sessions` so editing/deleting sets or workouts never creates stale or orphaned PR records.
  - **Unified Frontend Shell & Accessibility**: Extract shared `/static/css/common.css` and `/static/js/common.js` (unified dark theme variables, single consistent navbar, toast notifications, `escapeHtml`, safe UUID/clipboard, auth sign-out button, fetch wrapper redirecting to `/login` on 401), move each page's inline JS to `/static/js/{gym,dashboard,coach,config,login}.js`, and update `<meta name="viewport">` to `width=device-width, initial-scale=1.0` (removing `maximum-scale=1.0, user-scalable=no`).
- **Rationale**:
  - Fulfills Constitution Principle I exportability, removes dead storage that would drift after adding set deletion, and cuts ~1,000+ lines of duplicated CSS/navbar boilerplate while enabling strict CSP.

---

## R9. Container Hardening, Reusable HTTP Pooling & Automated Quality Gates (`FR-001`, `FR-002`, `FR-036`, `FR-037`)

- **Decision**:
  - **Dockerfile & Entrypoint**: Add `docker-entrypoint.sh` that runs `alembic upgrade head` before `exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}` (with `--proxy-headers` when `TRUST_PROXY_HEADERS=true`). Create non-root user `coach3`, remove duplicate `src/` copy (install dependencies without duplicating source tree), and add `HEALTHCHECK` calling `curl -f http://localhost:8000/health`.
  - **Docker Compose**: Bind Postgres to `127.0.0.1:${POSTGRES_PORT:-5432}:5432`, enforce `ENCRYPTION_KEY: ${ENCRYPTION_KEY:?ENCRYPTION_KEY must be set}`, pass `COACH3_PASSPHRASE`, `ALLOWED_ORIGINS`, `TRUST_PROXY_HEADERS`, `POLAR_REDIRECT_URI`, `CONCEPT2_REDIRECT_URI`, and `SYNC_INTERVAL_MINUTES`.
  - **Shared HTTP Client Lifecycle**: Provide a shared `httpx.AsyncClient` managed via app `lifespan` (or clean adapter lifecycle) for connection pooling, while remaining easily injectable/mockable in tests.
  - **Single Transaction Ownership & Default User Helper**: Extract `src/core/deps.py` (`get_or_create_default_user` using single-row safe creation + `get_or_create_default_hr_profile` with unified `max_hr=185` defaults). Keep service methods flushing (`await db.flush()`) rather than committing mid-unit-of-work, letting `get_db()` own the commit/rollback boundary (except explicit background/sync transaction managers).
  - **Quality Gates**: Add `ruff`, `mypy`, and `defusedxml` to `pyproject.toml`, remove `ignore::DeprecationWarning`, set `asyncio_default_fixture_loop_scope = "function"`, add an `autouse` `dependency_overrides.clear()` fixture in `conftest.py`, add PostgreSQL migration + integration test suite (run automatically when `TEST_DATABASE_URL` is configured, e.g., local Postgres / CI), and generate a pinned lockfile (`requirements.lock` / `uv.lock`).
- **Rationale**:
  - Prevents regressions like the Python 3.12 `NameError` and ensures every migration upgrade/downgrade and Postgres constraint is verified before release.
