# Tasks: Adaptive AI Coaching Engine with Dual-Engine Architecture

**Input**: Design documents from `specs/004-adaptive-ai-coaching/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/api-coaching.yaml`, `quickstart.md`)

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/`

**Tests**: Unit tests and integration tests included per user story requirements and acceptance criteria.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared utilities, privacy enforcement, and environment validation

- [X] T001 Verify Python 3.12 virtual environment dependencies in `.venv` for FastAPI, SQLAlchemy, Pydantic, httpx, and cryptography
- [X] T002 [P] Implement privacy scrubbing utility `PrivacyScrubberService` in `src/core/privacy.py` stripping athlete names, emails, raw GPS route coordinate arrays, and location names from prompt contexts per Constitution Principle I

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, schemas, database migrations, and dual-engine HTTP clients that MUST be complete before ANY user story can be implemented

⚠️ **CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create Coaching SQLAlchemy models in `src/models/coaching.py` with fields:
  - `LLMProviderConfig`: `id` (UUID PK), `user_id` (UUID FK users.id ON DELETE CASCADE, NOT NULL), `provider_type` (VARCHAR(50), NOT NULL: 'gemini', 'llama_cpp'), `endpoint_url` (VARCHAR(255), NOT NULL), `api_key_encrypted` (VARCHAR(500), NULLABLE), `model_name` (VARCHAR(100), NOT NULL), `temperature` (NUMERIC(3, 2), DEFAULT 0.7, NOT NULL), `max_tokens` (INTEGER, DEFAULT 2048, NOT NULL), `is_active` (BOOLEAN, DEFAULT FALSE, NOT NULL), `created_at` (TIMESTAMPTZ, DEFAULT NOW()), `updated_at` (TIMESTAMPTZ, DEFAULT NOW())
  - `CoachingPhilosophy`: `id` (UUID PK), `user_id` (UUID FK users.id ON DELETE CASCADE, NOT NULL), `name` (VARCHAR(100), NOT NULL), `description` (TEXT, NULLABLE), `target_zone2_pct` (NUMERIC(5, 2), DEFAULT 80.0, NOT NULL), `max_weekly_volume_ramp_pct` (NUMERIC(5, 2), DEFAULT 10.0, NOT NULL), `max_rpe_threshold` (NUMERIC(3, 1), DEFAULT 8.5, NOT NULL), `min_rest_days_per_week` (INTEGER, DEFAULT 2, NOT NULL), `primary_modality` (VARCHAR(50), DEFAULT 'hybrid', NOT NULL: 'endurance', 'strength', 'hybrid'), `custom_context_notes` (TEXT, NULLABLE), `is_active` (BOOLEAN, DEFAULT FALSE, NOT NULL), `created_at` (TIMESTAMPTZ, DEFAULT NOW()), `updated_at` (TIMESTAMPTZ, DEFAULT NOW())
  - `CoachingCritique`: `id` (UUID PK), `user_id` (UUID FK users.id ON DELETE CASCADE, NOT NULL), `workout_session_id` (UUID FK workout_sessions.id ON DELETE SET NULL, NULLABLE), `start_date` (TIMESTAMPTZ, NULLABLE), `end_date` (TIMESTAMPTZ, NULLABLE), `philosophy_id` (UUID FK coaching_philosophies.id ON DELETE SET NULL, NULLABLE), `provider_used` (VARCHAR(50), NOT NULL), `adherence_score` (NUMERIC(4, 1), NOT NULL), `summary_markdown` (TEXT, NOT NULL), `adherence_details` (JSONB, DEFAULT '{}'), `strain_assessment` (JSONB, DEFAULT '{}'), `recommendations` (JSONB, DEFAULT '[]'), `created_at` (TIMESTAMPTZ, DEFAULT NOW())
  - `TrainingSchedulePlan`: `id` (UUID PK), `user_id` (UUID FK users.id ON DELETE CASCADE, NOT NULL), `philosophy_id` (UUID FK coaching_philosophies.id ON DELETE SET NULL, NULLABLE), `target_goal` (VARCHAR(255), NOT NULL), `start_date` (DATE, NOT NULL), `end_date` (DATE, NOT NULL), `horizon_days` (INTEGER, DEFAULT 7, NOT NULL), `summary_markdown` (TEXT, NOT NULL), `status` (VARCHAR(50), DEFAULT 'active', NOT NULL: 'active', 'completed', 'superseded'), `created_at` (TIMESTAMPTZ, DEFAULT NOW()), `updated_at` (TIMESTAMPTZ, DEFAULT NOW())
  - `ScheduledWorkout`: `id` (UUID PK), `plan_id` (UUID FK training_schedule_plans.id ON DELETE CASCADE, NOT NULL), `target_date` (DATE, NOT NULL), `discipline` (VARCHAR(50), NOT NULL: 'outdoor_run', 'indoor_row', 'erg_bike', 'strength', 'rest'), `title` (VARCHAR(255), NOT NULL), `planned_duration_min` (INTEGER, DEFAULT 45, NOT NULL), `target_distance_m` (NUMERIC(10, 2), NULLABLE), `target_zone` (VARCHAR(50), NULLABLE), `target_rpe` (NUMERIC(3, 1), NULLABLE), `strength_exercises` (JSONB, NULLABLE), `notes` (TEXT, NULLABLE), `is_completed` (BOOLEAN, DEFAULT FALSE, NOT NULL), `created_at` (TIMESTAMPTZ, DEFAULT NOW())
- [X] T004 [P] Register coaching models in `src/models/__init__.py`
- [X] T005 Create Alembic migration script `alembic/versions/004_coaching_schema.py` creating tables `llm_provider_configs`, `coaching_philosophies`, `coaching_critiques`, `training_schedule_plans`, `scheduled_workouts` and seeding default philosophies
- [X] T006 [P] Create Pydantic v2 schemas in `src/schemas/coaching.py` for provider configs, philosophies, workout critiques, schedule plans, and scheduled workouts per `contracts/api-coaching.yaml`
- [X] T007 Implement dual-engine HTTP clients `BaseLLMClient`, `GeminiClient`, and `LlamaCppClient` in `src/services/llm_client.py` using `httpx` with structured JSON output handling

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Retrospective Workout Critique & Philosophy Adherence (Priority: P1) 🎯 MVP

**Goal**: Analyze completed workouts or date windows against the active coaching philosophy, evaluating intensity discipline (Zone 2 adherence), RPE thresholds, and recovery recommendations.

**Independent Test**: Submit a workout session for analysis; verify that the critique correctly evaluates philosophy adherence, flags gray-zone intensity or high-RPE fatigue, and provides actionable recommendations.

### Tests for User Story 1 ⚠️

- [X] T008 [P] [US1] Create unit tests in `tests/unit/test_coaching_service.py` for workout metric extraction, prompt assembly, and critique JSON response parsing

### Implementation for User Story 1

- [X] T009 [US1] Implement retrospective analysis engine `analyze_workout()` in `src/services/coaching_service.py` combining workout sessions, HR zone aggregates, strength sets, and philosophy rules into structured prompts dispatched to active LLM provider
- [X] T010 [US1] Implement endpoint `POST /api/v1/coaching/analyze` in `src/api/coaching.py` returning structured coaching critiques
- [X] T011 [US1] Mount coaching API router under `/api/v1/coaching` in `src/api/router.py` and register in `src/main.py`

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Forward-Looking Adaptive Training Schedule Generation (Priority: P1)

**Goal**: Synthesize periodized 7-day or 14-day training schedules with discrete daily workouts tailored to athlete goals, respecting volume ramp limits ($\le 10\%$) and rest day constraints.

**Independent Test**: Request a 7-day training plan for a target goal; verify that periodized workouts are generated, volume progression limits are honored, and individual `ScheduledWorkout` entities are saved in the database.

### Tests for User Story 2 ⚠️

- [X] T012 [P] [US2] Add unit tests in `tests/unit/test_coaching_service.py` validating 7-day and 14-day schedule generation, volume ramp rate limits ($\le 10\%$), and rest-day constraints

### Implementation for User Story 2

- [X] T013 [US2] Implement forward schedule generator `generate_forward_plan()` in `src/services/coaching_service.py` producing `TrainingSchedulePlan` and individual `ScheduledWorkout` entities
- [X] T014 [US2] Implement endpoints `POST /api/v1/coaching/plan` and `GET /api/v1/coaching/plans/active` in `src/api/coaching.py`

**Checkpoint**: At this point, User Stories 1 and 2 work independently and provide complete analysis and planning loops.

---

## Phase 5: User Story 3 - Dual-Engine LLM Selection, Health Checks & Privacy Safeguards (Priority: P2)

**Goal**: Enable users to configure, test, and switch between Google Gemini API and local homelab `llama.cpp` inference engines with zero server restarts and guaranteed PII/GPS stripping.

**Independent Test**: Switch active provider between Gemini and `llama.cpp`, execute provider health checks, and verify that outbound prompt payloads contain zero athlete names, emails, or GPS route points.

### Tests for User Story 3 ⚠️

- [X] T015 [P] [US3] Create unit tests in `tests/unit/test_privacy.py` and `tests/unit/test_llm_client.py` validating PII/GPS stripping and provider health check responses

### Implementation for User Story 3

- [X] T016 [US3] Implement provider configuration management and health check service in `src/services/llm_client.py` validating live connectivity, measuring latency, and encrypting/decrypting API keys
- [X] T017 [US3] Implement endpoints `GET /api/v1/coaching/providers`, `POST /api/v1/coaching/providers`, `POST /api/v1/coaching/providers/{id}/activate`, and `POST /api/v1/coaching/providers/{id}/test` in `src/api/coaching.py`

**Checkpoint**: At this point, User Stories 1, 2, and 3 are all functional and testable independently.

---

## Phase 6: User Story 4 - Philosophy Configuration, Custom Rule Steering & Manual Context Ingestion (Priority: P2)

**Goal**: Allow athletes to inspect, create, and customize coaching philosophies, adjust quantitative steering parameters, and manually load custom context text (methodology notes, injury constraints, coach rules) that steer all AI prompts.

**Independent Test**: Create a philosophy with custom context notes (e.g. "avoid conventional deadlifts due to lumbar strain"); run analysis/planning and verify the AI coach obeys the manual rules.

### Tests for User Story 4 ⚠️

- [X] T018 [P] [US4] Add unit tests in `tests/unit/test_philosophy_service.py` validating preset seeding, custom rule threshold overrides, and manual context note persistence

### Implementation for User Story 4

- [X] T019 [US4] Implement philosophy management service in `src/services/philosophy_service.py` managing CRUD, active philosophy selection, and manual context note injection into prompt context
- [X] T020 [US4] Implement endpoints `GET /api/v1/coaching/philosophies`, `POST /api/v1/coaching/philosophies`, and `POST /api/v1/coaching/philosophies/{id}/activate` in `src/api/coaching.py`

**Checkpoint**: At this point, User Stories 1, 2, 3, and 4 are all functional and testable independently.

---

## Phase 7: User Story 5 - Interactive Web Coaching Interface (Priority: P2)

**Goal**: Serve a responsive mobile & desktop web interface at `/coach` for provider management, health tests, philosophy customization with manual context editor, critique viewer, and calendar schedule checklist.

**Independent Test**: Load `http://localhost:8001/coach` in desktop and mobile Safari; verify provider health cards, philosophy editor with custom notes, critique view, and 7-day schedule calendar rendering without errors.

### Implementation for User Story 5

- [X] T021 [US5] Create interactive coaching interface in `src/static/coach.html` with provider status cards, health test buttons, philosophy sliders, manual context editor textarea, critique review card, and forward schedule calendar checklist
- [X] T022 [US5] Mount `/coach` route in `src/main.py` serving `src/static/coach.html` with unified navigation connecting `/gym`, `/dashboard`, and `/coach`

**Checkpoint**: The visual coaching web interface is fully interactive, responsive, and completely self-hosted with zero external CDN requests.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Integration testing, end-to-end quickstart validation, and performance verification

- [X] T023 [P] Create API integration tests in `tests/integration/test_coaching_api.py` covering provider switching, philosophy updates with context notes, retrospective critique, forward planning, and UI mounting
- [X] T024 Run complete automated test suite `pytest tests/ -v` and verify 100% pass rate
- [X] T025 Execute quickstart verification scenarios per `specs/004-adaptive-ai-coaching/quickstart.md` validating privacy scrubbing, dual-engine health checks, and sub-4s/sub-8s critique generation latencies

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion - BLOCKS all user stories.
- **User Story 1 (Phase 3 - P1)**: Depends on Phase 2 completion.
- **User Story 2 (Phase 4 - P1)**: Depends on Phase 2 and US1 completion.
- **User Story 3 (Phase 5 - P2)**: Depends on Phase 2 completion.
- **User Story 4 (Phase 6 - P2)**: Depends on Phase 2 completion.
- **User Story 5 (Phase 7 - P2)**: Depends on API endpoints from US1–US4.
- **Polish (Phase 8)**: Depends on completion of all user story phases.

### User Story Dependencies

```
[Phase 1: Setup]
       │
       ▼
[Phase 2: Foundational] (Models, Migration, Schemas, LLM Clients)
       │
       ├───────────────────────────────┬───────────────────────────────┐
       ▼                               ▼                               ▼
[Phase 3: US1 Critique (P1)]   [Phase 5: US3 Providers (P2)]   [Phase 6: US4 Philosophy (P2)]
       │                               │                               │
       ▼                               │                               │
[Phase 4: US2 Schedule (P1)]           │                               │
       │                               │                               │
       └───────────────────────────────┼───────────────────────────────┘
                                       ▼
                       [Phase 7: US5 Web Coaching UI (P2)]
                                       │
                                       ▼
                       [Phase 8: Polish & Validation]
```

---

## Parallel Opportunities

- **Phase 1**: T001 (venv validation) and T002 (PrivacyScrubber) can run in parallel.
- **Phase 2**: T004 (models __init__.py) and T006 (Pydantic schemas) can run in parallel with model/migration tasks.
- **Phase 3, 5, 6**: Once Foundational is complete, US1 (Critique), US3 (Providers), and US4 (Philosophy) can be implemented concurrently.
- **Tests**: T008 (US1 unit tests), T012 (US2 unit tests), T015 (US3 unit tests), and T018 (US4 unit tests) can all be written concurrently.
- **Polish**: T023 (integration tests) can be written in parallel with UI polish.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (PrivacyScrubber).
2. Complete Phase 2: Foundational (`coaching.py` models, Alembic migration 004, Pydantic schemas, `llm_client.py`).
3. Complete Phase 3: User Story 1 (Retrospective workout critique).
4. **STOP and VALIDATE**: Verify critique generation via mock/live provider and unit tests.

### Incremental Delivery

1. Complete Setup + Foundational → Database schema and LLM client ready.
2. Complete User Story 1 → Retrospective workout critique active (MVP).
3. Complete User Story 2 → Periodized forward microcycle schedule generator active.
4. Complete User Story 3 → Dual-engine provider switching & health checks verified.
5. Complete User Story 4 → Philosophy customization & manual context ingestion active.
6. Complete User Story 5 → Visual coaching interface mounted at `/coach`.
7. Complete Phase 8 → Full test suite passing and quickstart scenarios verified.
