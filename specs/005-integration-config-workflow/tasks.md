# Tasks: Integration Configuration & Workflow Stabilization

**Input**: Design documents from `specs/005-integration-config-workflow/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/api-config.yaml`, `quickstart.md`)

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/`

**Tests**: Unit tests, contract verification, and end-to-end integration tests are included for each user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared utilities, schema migration preparation, and dependency validation

- [X] T001 [P] Verify Python 3.12 dependencies in `.venv` for FastAPI, SQLAlchemy, Alembic, httpx, and cryptography
- [X] T002 [P] Create Alembic revision `alembic/versions/005_integration_config_and_demo.py` creating table `integration_client_configs` and adding `is_demo` column to `workout_sessions`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, Pydantic schemas, and encryption resolution services that MUST be complete before ANY user story can be implemented

⚠️ **CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create SQLAlchemy model `IntegrationClientConfig` in `src/models/integration.py` with fields: `id` (UUID PK), `provider` (VARCHAR(50) UNIQUE NOT NULL: 'polar', 'concept2'), `encrypted_client_id` (TEXT NOT NULL), `encrypted_client_secret` (TEXT NOT NULL), `redirect_uri` (VARCHAR(255) NULLABLE), `is_active` (BOOLEAN DEFAULT TRUE), `created_at` (TIMESTAMPTZ), `updated_at` (TIMESTAMPTZ)
- [X] T004 Add `is_demo` (BOOLEAN DEFAULT FALSE NOT NULL) column to `WorkoutSession` in `src/models/workout.py`
- [X] T005 [P] Register updated models in `src/models/__init__.py`
- [X] T006 [P] Create Pydantic v2 schemas in `src/schemas/config.py` for `SaveProviderCredentialsRequest`, `ProviderConfigSummary`, `VerificationResult`, `SeedResult`, and `ResetResult` per `contracts/api-config.yaml`
- [X] T007 Implement `ConfigService` in `src/services/config_service.py` with encryption/decryption methods and dynamic credential resolution (checking `integration_client_configs` table first with fallback to `.env` settings)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Guided Configuration & Integration Setup (Priority: P1) 🎯 MVP

**Goal**: Dedicated configuration UI and backend routes to save Polar/Concept2 credentials, handle OAuth callbacks via browser redirect, and verify connection health with live diagnostics.

**Independent Test**: Navigate to `/config`, enter client credentials, save them, complete OAuth redirect, and verify that "Verify Connection" returns active status and athlete profile info.

### Tests for User Story 1 ⚠️

- [X] T008 [P] [US1] Create unit tests in `tests/unit/test_config_service.py` for saving, masking, and resolving credentials with `.env` fallback
- [X] T009 [P] [US1] Create unit tests in `tests/unit/test_integration_verify.py` mocking Polar AccessLink and Concept2 Logbook profile endpoints and token refresh flows

### Implementation for User Story 1

- [X] T010 [US1] Implement verification methods `verify_connection()` in `src/adapters/polar.py` (checking Polar AccessLink user registration) and `src/adapters/concept2.py` (checking Concept2 Logbook `/api/users/me`)
- [X] T011 [US1] Implement `GET /api/v1/integrations/{provider}/callback` in `src/api/integrations.py` to handle OAuth authorization code redirects, store encrypted tokens, and redirect browser to `/config?status=connected&provider={provider}`
- [X] T012 [US1] Implement `POST /api/v1/integrations/{provider}/verify` in `src/api/integrations.py` to execute diagnostic ping and return `VerificationResult`
- [X] T013 [US1] Implement `GET /api/v1/config/integrations` and `POST /api/v1/config/integrations/{provider}` in `src/api/config.py`
- [X] T014 [US1] Create `src/static/config.html` with step-by-step setup guides, copyable callback URIs, credential inputs, Connect action, and live verification status badges
- [X] T015 [US1] Mount `/config` route in `src/main.py` serving `src/static/config.html`

**Checkpoint**: User Story 1 is fully functional and testable independently (MVP ready).

---

## Phase 4: User Story 2 - Unified Settings Hub for AI & Integrations (Priority: P1)

**Goal**: Consolidate AI Inference Provider configuration (Google Gemini API key and local `llama.cpp` endpoint) into `/config` alongside telemetry integrations.

**Independent Test**: Configure an LLM provider on `/config`, trigger test connection, and verify that the provider status updates across both `/config` and `/coach`.

### Tests for User Story 2 ⚠️

- [X] T016 [P] [US2] Create unit test in `tests/unit/test_ai_config_hub.py` verifying provider configuration updates from `/config` reflect in `/coach`

### Implementation for User Story 2

- [X] T017 [US2] Add AI Inference Provider card to `src/static/config.html` with provider type switcher (Gemini vs. llama.cpp), endpoint URL, API key input, and test ping button
- [X] T018 [US2] Wire AI configuration card in `src/static/config.html` to existing `POST /api/v1/coaching/providers` and `POST /api/v1/coaching/providers/{id}/test` endpoints

**Checkpoint**: User Stories 1 and 2 operate cohesively in the unified settings hub.

---

## Phase 5: User Story 3 - Cross-Module Navigation & Unified Shell (Priority: P1)

**Goal**: Embed a responsive, unified navigation bar across all four application views (`/gym`, `/dashboard`, `/coach`, `/config`) with active route highlighting.

**Independent Test**: Load each view (`/gym`, `/dashboard`, `/coach`, `/config`) and navigate seamlessly between them with a single click/tap on desktop and mobile.

### Tests for User Story 3 ⚠️

- [X] T019 [P] [US3] Create integration test in `tests/integration/test_static_routes.py` verifying all 4 web endpoints (`/gym`, `/dashboard`, `/coach`, `/config`) return 200 OK and render the shared navigation links

### Implementation for User Story 3

- [X] T020 [US3] Design responsive navigation component with links to Gym Mode (`/gym`), Volume Dashboard (`/dashboard`), AI Coach (`/coach`), and Settings (`/config`)
- [X] T021 [US3] Inject unified navigation header and active route styling into `src/static/gym.html`
- [X] T022 [US3] Inject unified navigation header and active route styling into `src/static/dashboard.html`
- [X] T023 [US3] Inject unified navigation header and active route styling into `src/static/coach.html`
- [X] T024 [US3] Inject unified navigation header and active route styling into `src/static/config.html`

**Checkpoint**: All 4 views are connected via the unified shell.

---

## Phase 6: User Story 4 - Local Demo Seed & Environment Resilience (Priority: P2)

**Goal**: Provide one-click UI and CLI workflows to seed realistic multi-modal workouts (runs, rows, strength) and safely purge demo records without deleting authentic athlete data.

**Independent Test**: Click "Load Sample Workouts" on `/config` or run `python -m src.scripts.seed_demo`; verify that volume charts and coaching critiques display populated data, then click "Reset Demo Data" to purge only demo records.

### Tests for User Story 4 ⚠️

- [X] T025 [P] [US4] Create unit test in `tests/unit/test_seed_service.py` validating that seeding creates running, rowing, and strength workouts with `is_demo=True`, and purging deletes ONLY `is_demo=True` sessions

### Implementation for User Story 4

- [X] T026 [US4] Implement `SeedService` in `src/services/seed_service.py` generating:
  - 1 Default user profile (if missing)
  - 1 Active Polarized 80/20 Coaching Philosophy
  - 3 Outdoor Running sessions with 5-zone HR distribution and GPS coordinates
  - 2 Concept2 Rowing sessions with split metrics and power
  - 2 Gym strength sessions with sets, reps, and RPE
  - Clean purge function `purge_demo_data()` deleting only `is_demo=True` sessions
- [X] T027 [US4] Create standalone CLI script `src/scripts/seed_demo.py` callable via `python -m src.scripts.seed_demo [--reset]`
- [X] T028 [US4] Implement endpoints `POST /api/v1/admin/demo/seed` and `DELETE /api/v1/admin/demo` in `src/api/admin.py` and mount in `src/api/router.py`
- [X] T029 [US4] Add "Demo & Testing Tools" card to `src/static/config.html` with "Load Sample Workouts" and "Reset Demo Data" action buttons

**Checkpoint**: Demo data seeding and clean reset fully operational in both UI and CLI.

---

## Phase 7: User Story 5 - Bug Triage & Graceful Error Handling (Priority: P2)

**Goal**: Ensure all API failure states (OAuth cancellations, expired tokens, unreachable LLM endpoints) display visible, human-readable toasts instead of silent failures or uncaught errors.

**Independent Test**: Trigger an action with an unconfigured or disconnected provider; verify that a clean error toast/banner appears with an actionable link to `/config`.

### Implementation for User Story 5

- [X] T030 [US5] Implement reusable JavaScript toast notification component in `src/static/config.html`, `src/static/gym.html`, `src/static/dashboard.html`, and `src/static/coach.html`
- [X] T031 [US5] Handle OAuth error query parameters (`?status=error&message=...`) in `src/static/config.html` to display red alert banner with resolution steps
- [X] T032 [US5] Add graceful fallback messaging on `/dashboard` and `/coach` when database is completely empty, directing users to `/config` to load demo data or connect Polar/Concept2

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end verification, documentation, and operational hygiene

- [X] T033 [P] Update `README.md` with complete getting started guide, local startup instructions (`alembic upgrade head`, `uvicorn src.main:app`), navigation layout, and setup guide overview
- [X] T034 [P] Run end-to-end verification scenarios A through E in `specs/005-integration-config-workflow/quickstart.md`
- [X] T035 Execute full test suite via `.venv/bin/pytest` and verify 100% test pass rate with zero regressions

---

## Phase 9: Convergence

- [X] T036 [US1] Fix OAuth authorization URL parameter duplication and add mandatory `scope='accesslink.read_all'` in `src/adapters/polar.py` and `src/adapters/concept2.py` per FR-002, FR-004 (contradicts)
- [X] T037 [US1] Implement on-demand "Sync Now" UI buttons and client handlers in `src/static/config.html` and `src/static/dashboard.html` calling `POST /api/v1/integrations/{provider}/sync` per FR-009, US1-AC5 (missing)

---

## Phase 10: Convergence

- [X] T038 Fix Polar AccessLink API v3 base URL (`https://www.polaraccesslink.com/v3`) and user registration endpoint in `src/adapters/polar.py` per Constitution II, FR-004, FR-009 (contradicts)
- [X] T039 Pass `account.account_id` as default `user_id` in `src/services/sync_service.py` and require valid user ID in `PolarAdapter.fetch_workouts_batch` for `/v3/users/{user_id}/exercise-transactions` per Constitution II, FR-009, US1-AC5 (missing)
- [X] T040 Update `normalize_polar_exercise` and `fetch_workouts_batch` in `src/adapters/polar.py` to support Polar AccessLink v3 hyphenated payload keys (`start-time`, `start-time-utc-offset`, `heart-rate`, `detailed-sport-info`) and multi-stream `/samples` endpoints per Constitution II, FR-009 (partial)
- [X] T041 Parse athlete display name from `first-name` and `last-name` in `PolarAdapter.verify_connection` per FR-004, US1-AC4 (partial)
- [X] T042 Update unit and integration tests in `tests/unit/test_polar_adapter.py` and `tests/unit/test_integration_verify.py` to validate Polar AccessLink v3 API structure, payload keys, and error recovery per Constitution II (partial)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories.
- **User Story 1 (Phase 3 - P1 MVP)**: Depends on Foundational Phase 2.
- **User Story 2 (Phase 4 - P1)**: Depends on Phase 3 (extends `/config` UI).
- **User Story 3 (Phase 5 - P1)**: Depends on Phase 3 (`/config` route must exist to link into navbar).
- **User Story 4 (Phase 6 - P2)**: Depends on Foundational Phase 2 (`is_demo` column).
- **User Story 5 (Phase 7 - P2)**: Depends on Phases 3–6 (hooks into UI error handling).
- **Polish (Phase 8)**: Depends on all user stories being complete.

### Parallel Opportunities

- T001, T002 can run in parallel.
- T005, T006, T007 can be authored in parallel once models are created.
- T008, T009 unit tests can be written in parallel.
- T016, T019, T025 unit tests can be written in parallel.
- T021, T022, T023, T024 navbar injections can run in parallel.
- T033, T034 can run in parallel during polish.

---

## Implementation Strategy (MVP First)

1. **Sprint 1 (Foundation & MVP)**:
   - Complete Phase 1 (Setup) and Phase 2 (Foundational).
   - Complete Phase 3 (User Story 1: Guided Configuration & Verification).
   - **VALIDATE**: Verify Polar/Concept2 credentials can be saved and verified in `/config`.
2. **Sprint 2 (Unified Shell & Settings Hub)**:
   - Complete Phase 4 (AI settings on `/config`).
   - Complete Phase 5 (Unified top navigation across all 4 screens).
   - **VALIDATE**: Seamless navigation between Gym, Dashboard, Coach, and Config.
3. **Sprint 3 (Demo Seeding & Polish)**:
   - Complete Phase 6 (Demo seed and reset).
   - Complete Phase 7 (Error toasts and empty state guidance).
   - Complete Phase 8 (README, full test suite pass).
