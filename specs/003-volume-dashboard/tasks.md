# Tasks: Unified Training Volume Modeling and Peak Performance Dashboard

**Input**: Design documents from `specs/003-volume-dashboard/` (`spec.md`, `plan.md`, `data-model.md`, `contracts/api-analytics.yaml`, `research.md`, `quickstart.md`)

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/`

**Tests**: Unit tests and integration tests included per user story requirements and acceptance criteria.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, vendor asset directories, and local dependencies

- [X] T001 Create vendor directory structure `src/static/vendor/` for self-hosted frontend libraries
- [X] T002 [P] Download or bundle standalone Chart.js v4 UMD distribution into `src/static/vendor/chart.umd.js` with zero external CDN dependencies
- [X] T003 [P] Verify Python 3.12 virtual environment dependencies in `.venv` for analytics and testing

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, schemas, and database migrations that MUST be complete before ANY user story can be implemented

⚠️ **CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create PersonalRecord SQLAlchemy model in `src/models/personal_record.py` with fields: `id` (UUID PK), `user_id` (UUID FK users.id ON DELETE CASCADE, NOT NULL), `discipline` (VARCHAR(50), NOT NULL: 'strength', 'outdoor_run', 'indoor_row', 'erg_bike'), `exercise_id` (UUID FK strength_exercises.id ON DELETE CASCADE, NULLABLE), `milestone_type` (VARCHAR(50), NOT NULL: 'weight_pr', 'estimated_1rm_pr', 'repetition_pr', '1_mile', '5k', '10k', '500m_erg', '2k_erg', '5k_erg'), `record_value` (NUMERIC(10, 2), NOT NULL), `record_unit` (VARCHAR(20), NOT NULL: 'lbs', 'kg', 'sec', 'sec_per_km', 'sec_per_500m', 'reps'), `estimated_1rm` (NUMERIC(7, 2), NULLABLE), `workout_session_id` (UUID FK workout_sessions.id ON DELETE SET NULL, NULLABLE), `strength_set_id` (UUID FK strength_sets.id ON DELETE SET NULL, NULLABLE), `achieved_at` (TIMESTAMPTZ, NOT NULL), `created_at` (TIMESTAMPTZ, DEFAULT NOW())
- [X] T005 [P] Register PersonalRecord model in `src/models/__init__.py`
- [X] T006 Create Alembic migration script `alembic/versions/003_personal_records.py` creating table `personal_records` and indexes `ix_personal_records_user_id`, `ix_personal_records_discipline`, `ix_personal_records_exercise_id`, and `ix_personal_records_achieved_at`
- [X] T007 [P] Create Pydantic v2 schemas in `src/schemas/analytics.py` for date window queries (`7d`, `30d`, `90d`, `ytd`, `all`), cardio volume metrics, strength volume metrics, personal record items, and unified volume summaries per `contracts/api-analytics.yaml`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Historical Cardiovascular Volume & Zone 2 Analytics (Priority: P1) 🎯 MVP

**Goal**: Aggregate running mileage, Zone 2 duration & percentage, Zone 1-5 heart rate distributions, and Concept2 erg meters/splits across rolling time windows.

**Independent Test**: Query `GET /api/v1/analytics/cardio` and `GET /api/v1/analytics/summary` across test sessions; verify total distance, Zone 2 minutes, and pace averages match database aggregates exactly.

### Tests for User Story 1 ⚠️

- [X] T008 [P] [US1] Create unit tests in `tests/unit/test_analytics_service.py` for cardio volume aggregation, weekly distance bucketing, Zone 2 duration & ratio calculation, and Concept2 split distribution

### Implementation for User Story 1

- [X] T009 [US1] Implement cardiovascular aggregation methods `get_cardio_metrics()` and `get_cardio_weekly_trends()` in `src/services/analytics_service.py` querying `workout_sessions` and `heart_rate_zones`
- [X] T010 [US1] Implement endpoints `GET /api/v1/analytics/cardio` and initial `GET /api/v1/analytics/summary` in `src/api/analytics.py`
- [X] T011 [US1] Mount analytics API router under `/api/v1/analytics` in `src/api/router.py` and register in `src/main.py`

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Strength Volume Load & Muscle Group Distribution (Priority: P1)

**Goal**: Calculate effective working sets (excluding warmups), total volume load ($\sum \text{sets} \times \text{reps} \times \text{weight}$), primary muscle group distributions, and isolated added calisthenic load.

**Independent Test**: Ingest warmup and working strength sets for barbell and calisthenic movements; verify `is_warmup=True` sets are excluded from effective set counts, external added weight is isolated, and muscle group volume maps match mathematical totals.

### Tests for User Story 2 ⚠️

- [X] T012 [P] [US2] Add unit tests in `tests/unit/test_analytics_service.py` for effective working set filtering (`is_warmup=false`), total volume load math, muscle group categorization, and added calisthenic load aggregation

### Implementation for User Story 2

- [X] T013 [US2] Implement strength aggregation methods `get_strength_metrics()` and `get_muscle_group_distribution()` in `src/services/analytics_service.py` querying `strength_sets` joined with `strength_exercises`
- [X] T014 [US2] Implement endpoint `GET /api/v1/analytics/strength` and integrate strength volume load and effective sets into `GET /api/v1/analytics/summary` in `src/api/analytics.py`

**Checkpoint**: At this point, User Stories 1 and 2 work independently and combine into unified summaries.

---

## Phase 5: User Story 3 - Historical Personal Records (PR) & Peak Performance Tracking (Priority: P2)

**Goal**: Deterministically detect and rank all-time and rolling window Personal Records: Epley estimated 1RM/5RM capped at sets $\le 10$ reps, absolute weight PRs, repetition PRs, and endurance milestone benchmarks (1 mile, 5k, 10k, 500m erg, 2k erg, 5k erg) within $\pm 3\%$ distance tolerance.

**Independent Test**: Submit sets with varied reps/weights and cardio sessions near milestone distances; verify Epley estimates are capped at $\le 10$ reps, endurance distances match within $\pm 3\%$, and PR audit records are correctly identified and persisted.

### Tests for User Story 3 ⚠️

- [X] T015 [P] [US3] Create unit tests in `tests/unit/test_pr_detector.py` validating Epley 1RM formula ($w \times (1 + r/30)$), 10-rep cap boundary, 5RM formula ($\text{1RM}/1.1667$), repetition PRs for bodyweight moves, and $\pm 3\%$ endurance distance matching

### Implementation for User Story 3

- [X] T016 [US3] Implement PR detection engine `PRDetectorService` in `src/services/pr_detector.py` for evaluating strength set PRs, cardio milestone PRs, and querying historical bests
- [X] T017 [US3] Implement endpoint `GET /api/v1/analytics/prs` in `src/api/analytics.py` supporting window filters and discipline filtering

**Checkpoint**: At this point, User Stories 1, 2, and 3 are all functional and testable independently.

---

## Phase 6: User Story 4 - Interactive Visual Web Dashboard with Responsive Charts (Priority: P2)

**Goal**: Serve a self-hosted, responsive visual dashboard at `/dashboard` rendering interactive Chart.js charts (weekly mileage bars, Zone 2 doughnut, volume load trend curve, muscle group sets radar/bar, and PR trophy cards) with client-side rolling date-window filters (`7D`, `30D`, `90D`, `YTD`, `All`).

**Independent Test**: Load `http://localhost:8001/dashboard` in a browser; verify zero external CDN calls, verify all 4 charts render with mock or ingested data, and verify tapping date filters smoothly refreshes all charts and KPI summary tiles.

### Implementation for User Story 4

- [X] T018 [US4] Create interactive mobile and desktop dashboard interface in `src/static/dashboard.html` with KPI summary cards, filter pills, PR showcase, and Chart.js visualizations referencing local `/static/vendor/chart.umd.js`
- [X] T019 [US4] Mount `/dashboard` route in `src/main.py` serving `src/static/dashboard.html` with navigation links connecting `/gym` and `/dashboard`

**Checkpoint**: The visual web dashboard is fully interactive, responsive, and completely self-hosted with zero external network requests.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration testing, end-to-end quickstart validation, and performance verification

- [X] T020 [P] Create API integration tests in `tests/integration/test_analytics_api.py` covering `/summary`, `/cardio`, `/strength`, `/prs`, and `/dashboard` endpoints
- [X] T021 Run complete automated test suite `pytest tests/ -v` and verify 100% pass rate
- [X] T022 Execute quickstart verification scenarios per `specs/003-volume-dashboard/quickstart.md` validating sub-120ms response latencies and offline dashboard rendering

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion - BLOCKS all user stories.
- **User Story 1 (Phase 3 - P1)**: Depends on Phase 2 completion. Can proceed independently of other stories.
- **User Story 2 (Phase 4 - P1)**: Depends on Phase 2 completion. Integrates with `/summary` alongside US1.
- **User Story 3 (Phase 5 - P2)**: Depends on Phase 2 completion. Operates on strength and cardio data structures.
- **User Story 4 (Phase 6 - P2)**: Depends on API endpoints from US1, US2, and US3 to populate all visual cards.
- **Polish (Phase 7)**: Depends on completion of all user story phases.

### User Story Dependencies

```
[Phase 1: Setup]
       │
       ▼
[Phase 2: Foundational] (Models, Schemas, Migration)
       │
       ├───────────────────────────────┬───────────────────────────────┐
       ▼                               ▼                               ▼
[Phase 3: US1 Cardio (P1)]     [Phase 4: US2 Strength (P1)]    [Phase 5: US3 PRs (P2)]
       │                               │                               │
       └───────────────────────────────┼───────────────────────────────┘
                                       ▼
                       [Phase 6: US4 Dashboard UI (P2)]
                                       │
                                       ▼
                       [Phase 7: Polish & Validation]
```

### Parallel Opportunities

- **Phase 1**: T002 (Chart.js bundle) and T003 (venv dependency check) can run in parallel.
- **Phase 2**: T005 (export model) and T007 (Pydantic schemas) can run in parallel with model/migration tasks.
- **Phase 3 & 4**: US1 (Cardio) and US2 (Strength) can be implemented in parallel once Foundational is complete.
- **Tests**: T008 (US1 unit tests), T012 (US2 unit tests), and T015 (US3 unit tests) can all be written in parallel.
- **Polish**: T020 (integration tests) can be written in parallel with dashboard final touches.

---

## Parallel Example: User Stories 1 & 2

```bash
# Developer A working on User Story 1 (Cardio):
Task: T008 [P] [US1] Create unit tests in tests/unit/test_analytics_service.py
Task: T009 [US1] Implement cardiovascular aggregation methods in src/services/analytics_service.py

# Developer B working on User Story 2 (Strength):
Task: T012 [P] [US2] Add unit tests in tests/unit/test_analytics_service.py
Task: T013 [US2] Implement strength aggregation methods in src/services/analytics_service.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (vendor directory, Chart.js).
2. Complete Phase 2: Foundational (`PersonalRecord` model, Alembic migration 003, Pydantic schemas).
3. Complete Phase 3: User Story 1 (Cardio analytics & summary endpoint).
4. **STOP and VALIDATE**: Verify cardio distance, weekly breakdown, and Zone 2 minutes via `curl` and unit tests.

### Incremental Delivery

1. Complete Setup + Foundational → Database schema and Pydantic validation ready.
2. Complete User Story 1 → Cardiovascular endurance analytics available via API (MVP).
3. Complete User Story 2 → Resistance training volume load and muscle groups available via API.
4. Complete User Story 3 → Deterministic PR engine (Epley 1RM, milestone matching) active.
5. Complete User Story 4 → Visual web dashboard mounted at `/dashboard` rendering all metrics interactively.
6. Complete Phase 7 → Full test suite passing and quickstart scenarios verified.
