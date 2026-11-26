# Implementation Plan: Comprehensive Security, Data Integrity, Reliability, and Quality Remediation

**Branch**: `007-remediation` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-remediation/spec.md`

## Summary

Remediate every P0, P1, P2, and systems-engineering gap uncovered in the full Coach3 codebase audit across security, data sovereignty, container/startup reliability, lossless Polar/Concept2 synchronization, Gym Mode parsing & offline resilience, analytics/timezone accuracy, query scalability, everyday CRUD + lossless ZIP export, unified accessible frontend architecture, and automated PostgreSQL/static-analysis quality gates. All decisions stay strictly self-hosted with minimal operational dependencies (leveraging Python stdlib `scrypt`, `zipfile`, `csv`, `zoneinfo`, and PostgreSQL advisory locks / partial unique indexes).

## Technical Context

**Language/Version**: Python 3.12+ (matching `python:3.12-slim` container target; verified compatible with 3.12–3.15)  
**Primary Dependencies**: FastAPI, Uvicorn, Pydantic v2 / pydantic-settings, SQLAlchemy 2.0 (asyncpg / aiosqlite), Alembic, APScheduler, httpx, cryptography (Fernet), RapidFuzz, defusedxml (safe GPX XML parsing)  
**Storage**: PostgreSQL 16 (production & real-DB migration/integration tests); SQLite (`aiosqlite`) retained for fast unit/API tests using dialect-safe `JSON().with_variant(JSONB, "postgresql")`  
**Testing**: pytest, pytest-asyncio (`asyncio_default_fixture_loop_scope = "function"`, zero suppressed `DeprecationWarning`), ruff (lint + Bandit security rules `S`), mypy (static type checking), PostgreSQL Alembic round-trip tests  
**Target Platform**: Self-hosted Linux Docker containers (homelab / home server) & macOS local development; desktop browsers and iPhone Safari clients (LAN HTTP & HTTPS reverse proxy)  
**Project Type**: Single-repository self-hosted web service (FastAPI REST backend + modular vanilla HTML/CSS/JS frontend)  
**Performance Goals**: Dashboard workout list (`limit=50..200`) < 500 ms with zero raw HR sample hydration; batched HR zone recalculation with bounded memory; bulk telemetry inserts  
**Constraints**: 100% self-hosted data sovereignty; zero external cloud services required; offline-buffered mobile gym set submission; strict `script-src 'self'` CSP; non-root container execution; lossless upgrade from migration `005`  
**Scale/Scope**: Single-athlete multi-year training history (thousands of workouts, millions of 1Hz HR/GPS telemetry rows, 4 web interfaces + `/login`, ~44 functional requirements)

## Constitution Check

*GATE: Evaluated pre-research and re-evaluated post-design.*

| Principle / Standard | Pre-Design Status | Post-Design Verification |
| :--- | :---: | :--- |
| **I. Self-Hosted Architecture & Data Sovereignty** | PASS (closes active violations) | `FR-003`–`FR-009` enforce mandatory encryption key, auth, strict CORS, header-only Gemini keys, SSRF blocks, and full PII scrubbing across system prompts, context notes, and goals. `FR-032` adds single-click lossless ZIP (JSON + CSV) export. |
| **II. Modular Ingestion & Source Isolation** | PASS (closes active violations) | `FR-011`–`FR-017` keep Polar/Concept2 adapters decoupled while adding deferred Polar commit (`commit_batch`), error propagation + 401-only refresh, full Concept2 pagination, exact units, concurrent upsert idempotency, and per-account scheduler isolation. |
| **III. Multimodal Ergonomics & Natural Language Robustness** | PASS (closes active violations) | `FR-020`–`FR-024` unify exercise UUIDs, fix preposition-less weight parsing & default units, stop forcing gibberish matches, render/commit multi-clause statements, honor exercise edits, fix voice audit diff, add LAN HTTP fallbacks, and add `localStorage` offline queue. |
| **IV. Unified Volume Modeling & Peak Performance Analytics** | PASS (closes active violations) | `FR-025`–`FR-029`, `FR-038` unify Epley 1RM across Dashboard & PRs, tie 1RM to displayed lift, exclude warmups, bucket chronologically in athlete IANA timezone, eliminate fabricated HR pace, and replace OOM list/recalc queries with SQL subqueries & batching. |
| **V. Philosophy-Steered, Adaptive AI Coaching** | PASS (closes active violations) | `FR-019`, `FR-031`, `FR-043` unify AI provider config, fix broken coach error banner & philosophy edit wiping, add in-flight concurrency guard (`409`), validate LLM schedule invariants before saving, and fix new-athlete baseline math. |
| **Technical Architecture & Constraints** | PASS | Hardened non-root Docker container with automatic Alembic migration entrypoint, DB-aware `/health`, localhost-bound Postgres, reverse-proxy support, pinch-to-zoom accessibility, and offline mobile gym buffering. |
| **Development Workflow & Quality Standards** | PASS | Spec Kit lifecycle followed (`spec.md` → `plan.md` → `tasks.md` → `implement`); adds ruff, mypy, real PostgreSQL migration upgrade/downgrade tests, contract tests, and unsuppressed warnings. |

*Gate Result*: **PASS — zero unjustified Constitution violations.**

## Project Structure

### Documentation (this feature)

```text
specs/007-remediation/
├── plan.md                         # This file (/speckit-plan output)
├── research.md                     # Phase 0 architectural & security decisions
├── data-model.md                   # Phase 1 schema remediation (migration 006) & entities
├── quickstart.md                   # Phase 1 runnable end-to-end validation guide
├── contracts/
│   └── api-remediation.yaml        # Phase 1 OpenAPI 3.1 contract for new/hardened endpoints
├── checklists/
│   └── requirements.md             # Spec quality checklist (16/16 passed)
└── tasks.md                        # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
docker-entrypoint.sh                # NEW: runs alembic upgrade head then execs uvicorn
Dockerfile                          # MODIFIED: non-root user, single src layout, HEALTHCHECK, entrypoint
docker-compose.yml                  # MODIFIED: 127.0.0.1 Postgres bind, required ENCRYPTION_KEY, full env passthrough
pyproject.toml                      # MODIFIED: defusedxml, ruff, mypy, pytest-asyncio loop scope, no DeprecationWarning hide
requirements.lock                   # NEW: reproducible pinned dependency lockfile
.env.example                        # MODIFIED: remove hardcoded Fernet default; add COACH3_PASSPHRASE, ALLOWED_ORIGINS, TRUST_PROXY_HEADERS

alembic/versions/
├── 002_gym_mode_schema.py          # MODIFIED: clean dialect guard, server_defaults, reversible downgrade
└── 006_remediation_hardening.py    # NEW: users.timezone/passphrase_hash, oauth_states, strength_sets.submission_key,
                                    #      api_key_encrypted->Text, partial unique active indexes, HR zone checks,
                                    #      drop duplicate indexes & dead personal_records table (reversible downgrade)

src/
├── main.py                         # MODIFIED: lifespan (startup orphan sync sweep, catalog DB load, shared httpx pool,
│                                   #           graceful scheduler drain & engine.dispose), CORS lockdown, security headers,
│                                   #           auth middleware, request-id middleware, DB-aware /health, /login route
├── core/
│   ├── auth.py                     # NEW: scrypt passphrase verify, HMAC session cookie, localhost bypass guard, login rate limiter
│   ├── config.py                   # MODIFIED: mandatory ENCRYPTION_KEY (non-test), auth/CORS/proxy/scrub/timeout settings
│   ├── database.py                 # MODIFIED: pool sizing, statement timeout, clean engine disposal
│   ├── deps.py                     # NEW: shared race-safe get_or_create_default_user & get_or_create_default_hr_profile
│   ├── http_client.py              # NEW: shared httpx client helpers + exponential backoff/Retry-After + SSRF URL validator
│   ├── logging.py                  # NEW: structured JSON logging, request_id contextvar, credential/token redaction filter
│   ├── privacy.py                  # MODIFIED: phone/GPS coordinate/custom-term scrubbing across all prompt text
│   ├── scheduler.py                # MODIFIED: per-account isolated sessions, Postgres advisory lock, graceful drain, audit pruning
│   └── security.py                 # MODIFIED: key validation helper & safe decrypt_token_safe returning InvalidToken status
├── models/
│   ├── coaching.py                 # MODIFIED: Text api_key_encrypted, partial unique indexes, check constraints
│   ├── exercise.py                 # MODIFIED: remove lazy="selectin" on sets, deduplicate unique indexes
│   ├── integration.py              # MODIFIED: dialect-safe JSON_TYPE, OAuthState model, remove redundant index
│   ├── personal_record.py          # REMOVED: dead unused table dropped in migration 006
│   ├── strength_set.py             # MODIFIED: submission_key column & clean unique key
│   ├── user.py                     # MODIFIED: timezone, passphrase_hash, updated HR bounds/zone ordering constraints
│   ├── voice_log.py                # MODIFIED: dialect-safe JSON_TYPE
│   └── workout.py                  # MODIFIED: dialect-safe JSON_TYPE, remove lazy="selectin" on strength_sets/voice_logs
├── schemas/
│   ├── analytics.py                # MODIFIED: pace_source / is_estimated metadata alignment
│   ├── auth.py                     # NEW: LoginRequest, AuthStatusResponse
│   ├── coaching.py                 # MODIFIED: strict bounds & Literal enums for providers, philosophies, LLM items, patch completion
│   ├── config.py                   # MODIFIED: optional client_id on update, decryption_error flag, diagnostics schemas
│   ├── gym.py                      # MODIFIED: original_parsed_sets on CommitSetsRequest
│   ├── profile.py                  # MODIFIED: HR profile @model_validator (resting >= 25, zone ordering) & AthletePreferences
│   └── workout.py                  # MODIFIED: Field(default_factory=list), WorkoutUpdateRequest, bounded GPXUploadRequest
├── adapters/
│   ├── base.py                     # MODIFIED: pending_commit_token on SyncBatchResult + commit_batch() hook
│   ├── concept2.py                 # MODIFIED: exact tenths-of-second math, BikeErg km pace, missing-ID guard, propagate errors + backoff
│   └── polar.py                    # MODIFIED: deferred commit_batch, sport mapping, missing-ID guard, defusedxml GPX, propagate errors + backoff
├── services/
│   ├── analytics_service.py        # MODIFIED: unified Epley 1RM, athlete timezone bucketing, chronological week sort, honest pace
│   ├── coaching_service.py         # MODIFIED: scrub system prompts/goals, per-user in-flight lock (409), plan invariant validator, timezone baseline
│   ├── config_service.py           # MODIFIED: graceful InvalidToken handling, reject masked bullets, optional client_id update
│   ├── exercise_catalog.py         # MODIFIED: deterministic uuid5 alignment + startup DB load
│   ├── export_service.py           # NEW: lossless ZIP (backup.json + workouts.csv + strength_sets.csv) generator
│   ├── gym_parser.py               # MODIFIED: import Any, bare weight regex, honor default_unit, stop forcing low-score match, remove dead code
│   ├── ingestion.py                # MODIFIED: preserve zones on metadata-only re-sync, Postgres ON CONFLICT upsert, bulk telemetry insert
│   ├── llm_client.py               # MODIFIED: x-goog-api-key header, SSRF validation, sanitized errors, timeouts/backoff
│   ├── metrics.py                  # NEW: single canonical calculate_epley_1rm() & unit conversion constants
│   ├── philosophy_service.py       # MODIFIED: flush-only unit of work, preserve fields cleanly
│   ├── pr_detector.py              # MODIFIED: reuse shared metrics.calculate_epley_1rm()
│   ├── seed_service.py             # MODIFIED: deterministic uuid5 exercises, unified HR defaults
│   └── sync_service.py             # MODIFIED: full pagination loop, deferred Polar commit, 401-only refresh, clean rollback + failed audit log
├── api/
│   ├── auth.py                     # NEW: /api/v1/auth/{login,logout,status}
│   ├── diagnostics.py              # NEW: /api/v1/system/diagnostics
│   ├── export.py                   # NEW: /api/v1/export
│   ├── admin.py                    # MODIFIED: auth-protected, shared transaction ownership
│   ├── analytics.py                # MODIFIED: shared deps, athlete timezone passed into analytics
│   ├── coaching.py                 # MODIFIED: bounded limits, 409 concurrency mapping, PATCH scheduled-workouts/{id}
│   ├── config.py                   # MODIFIED: clean error sanitization, partial secret update
│   ├── gym.py                      # MODIFIED: slug/id resolution, submission_key idempotency, true voice diff, GET session sets, DELETE set, UUID external_id
│   ├── integrations.py             # MODIFIED: DB-backed OAuth state CSRF verify, graceful decryption error, honest sync status, bounded limits
│   ├── profile.py                  # MODIFIED: batched HR zone recalculation, GET/PUT /preferences (timezone)
│   ├── router.py                   # MODIFIED: register auth, diagnostics, export routers
│   └── workouts.py                 # MODIFIED: SQL EXISTS/COUNT listing (zero HR sample hydration), user/status/window/offset filters, PATCH workout, bounded GPX
├── scripts/
│   └── seed_exercises.py           # MODIFIED: deterministic uuid5, fix duplicate alias, avoid async lazy load on aliases
└── static/
    ├── css/
    │   └── common.css              # NEW: unified dark theme, navbar, cards, toasts, accessible responsive styles
    ├── js/
    │   ├── common.js               # NEW: escapeHtml, formatMarkdown (safe), safeUUID, safeCopy, authFetch, toast, shared navbar
    │   ├── login.js                # NEW: passphrase sign-in controller
    │   ├── gym.js                  # NEW: multi-clause cards, exercise edit fix, session set reload, kg/BW volume, offline localStorage queue, delete set
    │   ├── dashboard.js            # NEW: preset window workout filter, load-more pagination, inline note edit, escaped rendering, honest pace label
    │   ├── coach.js                # NEW: fixed error banner, philosophy preserve, scheduled workout completion checkbox, safe markdown
    │   └── config.js               # NEW: placeholder-only masked Client ID, full AI load/save/activate, timezone selector, ZIP export button, System Health & Sync Diagnostics card
    ├── login.html                  # NEW: clean single-user passphrase login page
    ├── gym.html                    # MODIFIED: thin CSP-compliant shell using common.css + common.js + gym.js, pinch-to-zoom enabled
    ├── dashboard.html              # MODIFIED: thin CSP-compliant shell using common.css + common.js + dashboard.js, pinch-to-zoom enabled
    ├── coach.html                  # MODIFIED: thin CSP-compliant shell using common.css + common.js + coach.js, pinch-to-zoom enabled
    └── config.html                 # MODIFIED: thin CSP-compliant shell using common.css + common.js + config.js, pinch-to-zoom enabled

tests/
├── conftest.py                     # MODIFIED: autouse dependency_overrides cleanup, test encryption key & localhost auth bypass fixture
├── unit/
│   ├── test_auth_and_security.py   # NEW: scrypt/session cookie, brute-force 429, CORS, security headers/CSP, SSRF, InvalidToken graceful fallback
│   ├── test_gym_parser.py          # MODIFIED: add bare-weight, kg default_unit, gibberish ambiguity tests
│   ├── test_polar_adapter.py       # MODIFIED: deferred commit_batch, sport mapping, missing ID, defusedxml, HTTP error propagation
│   ├── test_concept2_adapter.py    # MODIFIED: <100s tenths-of-second math, BikeErg km pace, missing ID, HTTP error propagation
│   ├── test_privacy.py             # MODIFIED: phone/GPS/custom-term scrubbing + CoachingService system prompt & goal scrubbing
│   ├── test_analytics_service.py   # MODIFIED: unified Epley 1RM, timezone bucketing, cross-year week sort, honest pace
│   └── test_coaching_service.py    # MODIFIED: concurrency 409 lock, schedule invariant validation, new-athlete baseline
└── integration/
    ├── test_sync_resilience.py     # NEW: Polar DB-fail no-commit, Concept2 multi-page loop, 401 refresh, rollback, orphan recovery
    ├── test_gym_api.py             # MODIFIED: post-seed Bench Press commit, multi-candidate 1-set idempotency, prefix collision, voice diff, DELETE set
    ├── test_export_and_crud.py     # NEW: ZIP export (JSON+CSV), PATCH workout, PATCH scheduled workout, timezone preferences, diagnostics API
    └── test_postgres_migrations.py # NEW: real PostgreSQL alembic upgrade head -> downgrade base -> upgrade head & partial unique constraints
```

**Structure Decision**: Preserve the existing single-project `src/` + `tests/` + `alembic/` layout (no artificial monorepo split), while decomposing the four monolithic inline HTML files into thin CSP-compliant HTML shells backed by `/static/css/common.css` and `/static/js/*.js` modules.

## Complexity Tracking

No Constitution violations requiring exceptions.
