# Tasks: Core Data Ingestion & Telemetry Models

**Input**: Design documents from `/specs/001-data-ingestion/`  
**Prerequisites**: [plan.md](file:///Users/frankmurdock/coach3/specs/001-data-ingestion/plan.md), [spec.md](file:///Users/frankmurdock/coach3/specs/001-data-ingestion/spec.md), [data-model.md](file:///Users/frankmurdock/coach3/specs/001-data-ingestion/data-model.md), [contracts/api-ingestion.yaml](file:///Users/frankmurdock/coach3/specs/001-data-ingestion/contracts/api-ingestion.yaml), [quickstart.md](file:///Users/frankmurdock/coach3/specs/001-data-ingestion/quickstart.md)

## Format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to ([US1], [US2], [US3])
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, container orchestration, and runtime configuration

- [x] T001 Create project source and test directory structure per plan in `src/` and `tests/`
- [x] T002 Initialize Python project configuration and dependencies (`fastapi`, `uvicorn`, `pydantic>=2.0`, `pydantic-settings`, `sqlalchemy>=2.0`, `asyncpg`, `alembic`, `apscheduler`, `httpx`, `cryptography`, `pytest`, `pytest-asyncio`, `pytest-mock`) in `pyproject.toml`
- [x] T003 [P] Create Docker Compose service definition for PostgreSQL 16 (`postgres:16-alpine`) and Coach3 application in `docker-compose.yml`
- [x] T004 [P] Create multi-stage container build definition in `Dockerfile`
- [x] T005 [P] Create application environment settings with database and credential configuration in `src/core/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database engine, encryption utilities, ORM models, migrations, and base adapter interfaces  
**⚠️ CRITICAL**: Must complete before any user story implementation begins

- [x] T006 Implement async SQLAlchemy engine and session factory in `src/core/database.py`
- [x] T007 [P] Create base SQLAlchemy declarative model with timestamp mixin in `src/models/base.py`
- [x] T008 [P] Implement authenticated Fernet token encryption and decryption utilities in `src/core/security.py`
- [x] T009 [P] Create unit tests for token encryption and decryption in `tests/unit/test_security.py`
- [x] T010 Create `User` and `UserHeartRateProfile` models with constraints `CHECK (resting_hr > 30 AND max_hr < 240 AND resting_hr < max_hr)` in `src/models/user.py`
- [x] T011 [P] Create `IntegrationAccount` and `SyncAuditLog` models with `CHECK (provider IN ('polar', 'concept2'))` and `CHECK (status IN ('running', 'success', 'partial', 'failed'))` in `src/models/integration.py`
- [x] T012 [P] Create `WorkoutSession`, `HeartRateSample`, `GPSRoutePoint`, and `WorkoutSplit` models with `UNIQUE (provider, external_id)` and `CHECK (discipline IN ('outdoor_run', 'indoor_row', 'erg_bike'))` in `src/models/workout.py` and `src/models/telemetry.py`
- [x] T013 Initialize Alembic migration environment (`alembic.ini`, `alembic/env.py`) and generate initial database migration in `alembic/versions/001_initial_schema.py`
- [x] T014 [P] Define abstract base ingestion adapter class `BaseIngestionAdapter` in `src/adapters/base.py`
- [x] T015 [P] Implement local heart rate zone calculator for Zone 1 through Zone 5 in `src/services/zone_calculator.py`
- [x] T016 [P] Create unit tests for zone calculation boundaries in `tests/unit/test_zone_calculator.py`

**Checkpoint**: Foundation ready — database schema, ORM models, encryption, and base interfaces complete.

---

## Phase 3: User Story 1 - Polar Outdoor Running Ingestion (Priority: P1) 🎯 MVP

**Goal**: Ingest Polar outdoor running sessions, parse GPS route points and heart rate samples, compute Zone 1–5 durations locally, and persist canonical workout records.  
**Independent Test**: Provide Polar AccessLink OAuth credentials, ingest a sample run from mock fixtures, and verify that distance, duration, elevation, GPS coordinates, and Zone 2 durations are accurately stored.

### Tests for User Story 1
- [x] T017 [P] [US1] Create mock Polar AccessLink exercise and telemetry JSON fixtures in `tests/fixtures/polar_samples.json`
- [x] T018 [P] [US1] Create unit tests for Polar payload normalization, GPS extraction, and metric calculation in `tests/unit/test_polar_adapter.py`

### Implementation for User Story 1
- [x] T019 [P] [US1] Create Pydantic domain models for workout summaries and telemetry in `src/schemas/workout.py`
- [x] T020 [US1] Implement Polar AccessLink API client and data mapper in `src/adapters/polar.py`
- [x] T021 [US1] Implement workout ingestion service coordinator in `src/services/ingestion.py`
- [x] T022 [US1] Create integration test verifying end-to-end ingestion of a Polar run with GPS coordinates and Zone 2 durations in `tests/integration/test_polar_ingestion.py`

**Checkpoint**: User Story 1 fully functional and testable independently (MVP milestone reached).

---

## Phase 4: User Story 2 - Concept2 Erg Bike & Rower Ingestion (Priority: P2)

**Goal**: Ingest Concept2 Logbook rowing and bike erg workouts, map equipment types, and preserve stroke rate, wattage, split times, and interval splits.  
**Independent Test**: Authenticate with Concept2 Logbook credentials, fetch a rower and bike erg workout from fixtures, and verify that split times, stroke rates, and power are stored in `WorkoutSession` and `WorkoutSplit`.

### Tests for User Story 2
- [x] T023 [P] [US2] Create mock Concept2 Logbook rower and bike erg JSON fixtures with interval splits in `tests/fixtures/concept2_samples.json`
- [x] T024 [P] [US2] Create unit tests for Concept2 payload normalization, stroke/split mapping, and drag factor parsing in `tests/unit/test_concept2_adapter.py`

### Implementation for User Story 2
- [x] T025 [P] [US2] Create Pydantic schemas for Concept2 erg summaries and interval splits in `src/schemas/workout.py`
- [x] T026 [US2] Implement Concept2 Logbook API client and data mapper in `src/adapters/concept2.py`
- [x] T027 [US2] Extend ingestion coordinator in `src/services/ingestion.py` to persist Concept2 erg sessions and `WorkoutSplit` records
- [x] T028 [US2] Create integration test verifying end-to-end ingestion and split preservation for rower and bike erg workouts in `tests/integration/test_concept2_ingestion.py`

**Checkpoint**: User Stories 1 AND 2 are both independently functional and tested.

---

## Phase 5: User Story 3 - Unified Workout Inspection, Audit Logs & Ingestion Scheduler (Priority: P3)

**Goal**: Provide REST endpoints to inspect workouts, query telemetry streams, trigger on-demand syncs, run 60-minute background polling, and enforce idempotency and soft-sync.  
**Independent Test**: Trigger repeated sync operations to verify 0 duplicate workouts, check sync audit logs for item counts and timestamps, and verify endpoints via `contracts/api-ingestion.yaml`.

### Tests for User Story 3
- [x] T029 [P] [US3] Create integration test verifying sync idempotency produces 0 duplicates in `tests/integration/test_ingestion_idempotency.py`
- [x] T030 [P] [US3] Create integration test verifying soft-sync and upstream edit/deletion handling in `tests/integration/test_soft_sync.py`
- [x] T031 [P] [US3] Create API contract integration test verifying all endpoints in `src/api/` match `contracts/api-ingestion.yaml` in `tests/integration/test_api_endpoints.py`

### Implementation for User Story 3
- [x] T032 [P] [US3] Create Pydantic schemas for integrations, sync triggers, and sync audit logs in `src/schemas/integration.py`
- [x] T033 [P] [US3] Implement sync dispatcher and pagination backfill coordinator in `src/services/sync_service.py`
- [x] T034 [P] [US3] Implement APScheduler background service in `src/core/scheduler.py` executing 60-minute recurring sync
- [x] T035 [US3] Implement integration endpoints (OAuth URL, code exchange, manual sync trigger, sync audit logs) in `src/api/integrations.py`
- [x] T036 [US3] Implement workout query endpoints (list workouts, workout detail, telemetry streams) in `src/api/workouts.py`
- [x] T037 [P] [US3] Implement user HR profile endpoints (get/update HR profile) in `src/api/profile.py`
- [x] T038 [US3] Assemble FastAPI application, router registration, and startup/shutdown scheduler hooks in `src/main.py`

**Checkpoint**: All three user stories are complete, verified against contracts, and scheduled.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Environment bootstrapping, configuration examples, and end-to-end test verification

- [x] T039 [P] Create initial environment template in `.env.example`
- [x] T040 Execute end-to-end validation scenarios documented in `specs/001-data-ingestion/quickstart.md`
- [x] T041 Run full test suite with `pytest tests/ -v` and verify 100% pass rate

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: Independent — start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**.
- **User Story 1 (Phase 3)**: Depends on Phase 2 — MVP delivery.
- **User Story 2 (Phase 4)**: Depends on Phase 2 — can run in parallel with US1 or sequentially.
- **User Story 3 (Phase 5)**: Depends on Phase 2, integrates services from US1 & US2.
- **Polish (Phase 6)**: Runs after desired user stories are complete.

### User Story Dependencies
- **US1 (P1)**: Core foundation models (`WorkoutSession`, `HeartRateSample`, `GPSRoutePoint`).
- **US2 (P2)**: Shares `WorkoutSession`, adds `WorkoutSplit`.
- **US3 (P3)**: Exposes API routes and scheduler for all adapters.

---

## Parallel Execution Opportunities

- **Setup Phase**: T003 (`docker-compose.yml`), T004 (`Dockerfile`), and T005 (`config.py`) can run in parallel.
- **Foundational Phase**: T007 (`base.py`), T008 (`security.py`), T009 (`test_security.py`), T011 (`integration.py`), T012 (`telemetry.py`), T014 (`adapters/base.py`), T015 (`zone_calculator.py`), and T016 (`test_zone_calculator.py`) can all run in parallel.
- **Story Phases**: Once Foundational is complete, User Story 1 (Polar) and User Story 2 (Concept2) can be implemented in parallel.

---

## Implementation Strategy: MVP First

1. **Sprint 1 (MVP)**: Complete Phase 1 (Setup) + Phase 2 (Foundational) + Phase 3 (User Story 1).
   * *Deliverable*: Working backend that imports Polar running workouts with GPS tracks, stores them in PostgreSQL, and calculates Zone 2 cardio duration.
2. **Sprint 2**: Implement Phase 4 (User Story 2: Concept2 Erg).
   * *Deliverable*: Full endurance volume across running, rowing, and erg biking.
3. **Sprint 3**: Implement Phase 5 (User Story 3: Scheduler, Soft-Sync, and REST API).
   * *Deliverable*: Complete automated self-hosted pipeline with hourly background sync, idempotency, and query endpoints.
