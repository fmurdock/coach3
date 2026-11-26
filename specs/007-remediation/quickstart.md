# Quickstart Validation Guide: Coach3 Remediation (`007-remediation`)

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Contracts**: [api-remediation.yaml](contracts/api-remediation.yaml)

This guide defines the concrete end-to-end validation scenarios proving all P0, P1, P2, and systems-engineering remediation requirements work together.

---

## Prerequisites

- Python 3.12+ (matching the containerized runtime) and local `.venv`
- Docker & Docker Compose (for containerized boot + PostgreSQL migration validation)
- Generated Fernet key:
  ```bash
  .venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

---

## Scenario 1: Hardened Container Boot & Startup Security (`SC-001`, `SC-002`)

1. **Missing Key Rejection**: Start the app with `ENVIRONMENT=production` and empty `ENCRYPTION_KEY`.
   - **Expected**: Application refuses to boot with a clear validation error mentioning `ENCRYPTION_KEY`.
2. **Clean Container Boot**: Set `ENCRYPTION_KEY` and `COACH3_PASSPHRASE` in `.env` and launch:
   ```bash
   docker compose up --build -d
   ```
   - **Expected**:
     - Container boots on Python 3.12 with zero `NameError` or import failures.
     - Entrypoint automatically applies `alembic upgrade head` (including `006_remediation_hardening`).
     - Process runs as non-root user (`docker exec coach3-app id` shows non-zero UID).
     - `curl -i http://localhost:8000/health` returns `200` with `{"status": "healthy", "database": "connected"}` and strict security headers (`Content-Security-Policy`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`).
     - Stopping `db` causes `/health` to return `503` (`"database": "unreachable"`).
     - Postgres port is bound only to `127.0.0.1:5432` (not `0.0.0.0`).

---

## Scenario 2: Authentication, CORS, OAuth CSRF, XSS & PII Scrubbing (`SC-002`)

1. **Passphrase Login & Rate Limit**:
   - Unauthenticated `GET /api/v1/workouts` returns `401`; visiting `/dashboard` redirects to `/login`.
   - Submitting 6 wrong passphrases to `POST /api/v1/auth/login` triggers `429 Too Many Requests` with `Retry-After`.
   - Submitting the valid passphrase sets `coach3_session` (`HttpOnly`, `SameSite=Lax`) and unlocks all views.
2. **CORS Lockdown**:
   - Sending `Origin: https://evil.example` to `/api/v1/workouts` does not return `Access-Control-Allow-Origin: https://evil.example` or `*`.
3. **OAuth CSRF**:
   - Calling `GET /api/v1/integrations/polar/callback?code=abc&state=forged` redirects to `/config?status=error` without saving tokens.
4. **SSRF & Secret Safety**:
   - Attempting to save a `llama_cpp` provider with `endpoint_url: http://169.254.169.254/latest/meta-data` returns `422`/`400`.
   - Gemini requests transmit credentials via `x-goog-api-key` header (zero `?key=` in URLs or logs) and redact PII from `custom_context_notes` and `target_goal`.
5. **XSS Protection**:
   - Saving `<img src=x onerror=alert(1)>` in a workout note/title or rendering it in AI critique markdown displays literal text with zero script execution and passes strict `script-src 'self'` CSP.

---

## Scenario 3: Lossless Sync, Pagination, Concept2 Math & Diagnostics (`SC-003`, `SC-009`, `SC-010`)

1. **Automated Sync Contract Suite**:
   ```bash
   .venv/bin/pytest tests/unit/test_polar_adapter.py tests/unit/test_concept2_adapter.py tests/integration/test_sync_resilience.py -v
   ```
   - **Expected**:
     - Polar `commit_batch` is NOT called if local DB persistence raises an error.
     - Concept2 3-page history sync imports all 3 pages before clearing `sync_cursor` and updating `last_sync_at`.
     - Concept2 short intervals (`time=600`, `rest_time=900`) normalize to `60.0s` and `90.0s` (not `600s`/`900s`), and BikeErg pace maps to per-km pace.
     - HTTP `401` triggers refresh + retry; HTTP `429`/`503` retries with backoff; persistent errors record `SyncAuditLog.status == "failed"` after rollback.
     - Startup recovers orphaned `status="running"` sync audit rows to `"failed"`.
2. **Settings Diagnostics & Key Mismatch**:
   - Open `/config` and inspect **System Health & Sync Diagnostics**: verify DB status, scheduler next run, and recent sync audit table (with warning badge when a failed sync exists).
   - Start with a rotated `ENCRYPTION_KEY` against existing encrypted rows: `/config` still loads cleanly and flags affected credentials with a "Re-enter credentials" notice instead of HTTP 500.

---

## Scenario 4: Settings Credential Safety & Gym Mode End-to-End (`SC-004`)

1. **Masked Client ID Protection**:
   - On `/config`, save Polar Client ID + Secret, reload `/config`, verify Client ID field shows masked preview only as a placeholder (empty value), enter a new secret only, click Save, and confirm the real Client ID is preserved (not overwritten with `•••`).
2. **Post-Seed Gym Logging, Multi-Clause & Offline Queue**:
   - Click **Load Sample Workouts** on `/config`.
   - Open `/gym` and submit `"bench press 225 lbs 3x5 then pullups with extra 25 lbs 3x8"`.
   - **Expected**: Both exercises appear as editable staged cards; editing an exercise name and confirming saves both exercises cleanly with zero `UniqueViolation` or idempotency collisions; reloading `/gym` restores today's sets and accurate volume.
   - Toggle browser offline mode, confirm a set, verify it queues locally with a pending indicator, restore connectivity, and verify automatic idempotent sync.
   - Click Undo/Delete on a logged set and verify it is removed cleanly.

---

## Scenario 5: Dashboard Scalability, Timezone Accuracy, Export & CRUD (`SC-005`, `SC-006`, `SC-007`)

1. **Timezone Bucketing**:
   - Set Athlete Timezone to `America/Los_Angeles` on `/config`.
   - Log/seed a Sunday 18:00 local workout (Monday 02:00 UTC) and verify it appears in the Sunday week's Zone 2 / Resistance totals on `/dashboard`.
2. **Consistent 1RM & Honest Pace**:
   - Verify Resistance Volume estimated 1RM matches PR Showcase Epley 1RM for the same top lift, and runs without speed/GPS telemetry do not show fabricated HR-derived pace as measured speed.
3. **Workout Edit, Pagination & ZIP Export**:
   - Edit workout notes in the Dashboard drawer and confirm persistence.
   - Click **Export Training History (.zip)** on `/config`, unzip, and verify `backup.json`, `workouts.csv`, and `strength_sets.csv` contain 100% of authentic workouts, telemetry, strength sets, philosophies, and plans (and zero demo rows or encrypted secrets).

---

## Scenario 6: Full Quality Gate & PostgreSQL Migration Verification (`SC-008`)

```bash
# Static analysis & strict type checks
.venv/bin/ruff check src tests
.venv/bin/mypy src

# Full unit + integration suite (zero suppressed deprecation warnings)
.venv/bin/pytest -W default -v

# Real PostgreSQL migration upgrade/downgrade + integration suite
TEST_DATABASE_URL="postgresql+asyncpg://coach:coach_secret@127.0.0.1:5432/coach3_test" \
  .venv/bin/pytest tests/integration/test_postgres_migrations.py -v
```

- **Expected**: All checks pass with exit code `0`, zero deprecation warnings, and full `upgrade head` → `downgrade base` → `upgrade head` cleanliness.
