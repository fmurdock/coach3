# Tasks: Gym Mode Natural Language Workout Logging

**Feature**: `002-gym-voice-logging`  
**Input**: Design documents from `specs/002-gym-voice-logging/` (`plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`)  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api-voice-logging.yaml`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency installation and initial project setup

- [x] T001 Add `rapidfuzz>=3.6.0` to `pyproject.toml` and install dependencies in `.venv`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database models, migrations, schemas, and catalog service blocking all user stories

- [x] T002 Create `StrengthExercise` and `ExerciseAlias` models in `src/models/exercise.py` with fields `id` (UUID PK), `canonical_name` (VARCHAR(120), not null), `slug` (VARCHAR(120), unique, not null), `category` (VARCHAR(50), not null, values: 'barbell', 'dumbbell', 'bodyweight', 'machine', 'cable'), `primary_muscle_group` (VARCHAR(50), not null), `is_bodyweight` (BOOLEAN, default False), `default_unit` (VARCHAR(10), default 'lbs'), and `alias` (VARCHAR(120), unique, not null)
- [x] T003 [P] Create `StrengthSet` model in `src/models/strength_set.py` with fields `id` (UUID PK), `workout_session_id` (UUID FK to workout_sessions.id), `exercise_id` (UUID FK to strength_exercises.id), `set_index` (INTEGER, not null), `reps_completed` (INTEGER, not null), `target_reps` (INTEGER, nullable), `weight` (NUMERIC(7,2), default 0.0), `weight_unit` (VARCHAR(10), default 'lbs'), `is_bodyweight` (BOOLEAN, default False), `added_weight` (NUMERIC(7,2), default 0.0), `rpe` (NUMERIC(3,1), nullable), `is_warmup` (BOOLEAN, default False), `rest_seconds` (INTEGER, nullable), and `idempotency_key` (VARCHAR(100), unique, nullable)
- [x] T004 [P] Create `VoiceTranscriptionLog` model in `src/models/voice_log.py` with fields `id` (UUID PK), `user_id` (UUID FK to users.id), `workout_session_id` (UUID FK to workout_sessions.id, nullable), `raw_transcript` (TEXT, not null), `parsed_json` (JSONB, not null), `confidence_score` (FLOAT, not null), `was_edited` (BOOLEAN, default False), `final_confirmed_json` (JSONB, nullable), and `confirmed_at` (TIMESTAMPTZ, nullable)
- [x] T005 Create Alembic migration script in `alembic/versions/` creating tables `strength_exercises`, `exercise_aliases`, `strength_sets`, and `voice_transcription_logs`
- [x] T006 Implement exercise catalog seed data script in `src/scripts/seed_exercises.py` populating 120+ standard barbell, dumbbell, bodyweight, machine, and Olympic lifts with common synonyms
- [x] T007 [P] Create Pydantic schemas in `src/schemas/gym.py` implementing `ParseTranscriptRequest`, `ParsedSetCandidate`, `ParsedStageResponse`, `CommitSetsRequest`, `StrengthExercise`, and `StrengthSetResponse` per `specs/002-gym-voice-logging/contracts/api-voice-logging.yaml`
- [x] T008 Implement `ExerciseCatalogService` in `src/services/exercise_catalog.py` with in-memory caching, search by category, and RapidFuzz fuzzy alias matching

**Checkpoint**: Foundation ready — database schema, models, catalog service, and schemas are complete.

---

## Phase 3: User Story 1 - Compound Lifts with Instant Confirmation (Priority: P1) 🎯 MVP

**Goal**: Parse spoken compound barbell/dumbbell sets (e.g. "5 sets by 8 reps of back squat at 185 pounds"), return staged confirmation card, and atomically commit confirmed sets to the database.

**Independent Test**: Submit spoken phrases for compound lifts to `POST /api/v1/gym/parse`, verify structured set attributes (exercise, sets, reps, weight, unit), and commit to `POST /api/v1/gym/sessions/{id}/sets` to verify persistence in `strength_sets`.

### Tests for User Story 1
- [x] T009 [P] [US1] Unit tests for compound barbell and dumbbell regex/grammar parsing in `tests/unit/test_gym_parser.py`
- [x] T010 [P] [US1] Unit tests for exercise catalog search and alias matching in `tests/unit/test_exercise_catalog.py`

### Implementation for User Story 1
- [x] T011 [US1] Implement core deterministic regex grammar and plate math parser in `src/services/gym_parser.py` extracting canonical exercises, sets, reps, load, and unit
- [x] T012 [US1] Implement `POST /api/v1/gym/parse` endpoint in `src/api/gym.py` returning staged confirmation responses
- [x] T013 [US1] Implement `GET /api/v1/gym/exercises` and `GET /api/v1/gym/sessions/active` in `src/api/gym.py`
- [x] T014 [US1] Implement atomic set commit endpoint `POST /api/v1/gym/sessions/{session_id}/sets` in `src/api/gym.py` with idempotency key enforcement and audit logging in `voice_transcription_logs`
- [x] T015 [US1] Mount gym router in `src/api/router.py`
- [x] T016 [P] [US1] Integration tests for parse and commit workflow in `tests/integration/test_gym_api.py`

**Checkpoint**: User Story 1 (MVP) is fully functional and independently verified.

---

## Phase 4: User Story 2 - Calisthenic and Weighted Bodyweight Movements (Priority: P1)

**Goal**: Parse bodyweight exercises with or without added/assisted resistance (e.g. "3 sets of 12 pullups with an extra 30 pounds added" or "3 sets of 8 assisted dips minus 20 pounds"), distinguishing base bodyweight from external load.

**Independent Test**: Pass bodyweight phrases with positive added load, zero added load, and assisted counterbalance to `/api/v1/gym/parse` and confirm `is_bodyweight=True`, `weight=0.0`, and `added_weight` correctly isolated.

### Tests for User Story 2
- [x] T017 [P] [US2] Unit tests for bodyweight and added/assisted load parsing in `tests/unit/test_gym_parser.py`

### Implementation for User Story 2
- [x] T018 [US2] Extend `src/services/gym_parser.py` with bodyweight modifier patterns ("extra X lbs", "plus X lbs", "bodyweight only", "assisted minus X lbs")
- [x] T019 [US2] Update `src/api/gym.py` set commit logic to enforce bodyweight load constraints (`weight=0.0`, `added_weight=+/-X`)
- [x] T020 [P] [US2] Integration tests verifying bodyweight and weighted calisthenic set persistence in `tests/integration/test_gym_api.py`

**Checkpoint**: User Stories 1 and 2 are fully functional and independently verified.

---

## Phase 5: User Story 3 - Perceived Exertion (RPE) and Rest Interval Capture (Priority: P2)

**Goal**: Extract Rate of Perceived Exertion (RPE / RIR) and rest interval durations from spoken input (e.g. "did a heavy single at 315 on deadlift, felt like RPE 9, 3 minutes rest").

**Independent Test**: Submit spoken phrases with RPE ratings or reps-in-reserve and rest intervals, verifying `rpe` (numeric 1.0-10.0) and `rest_seconds` are accurately extracted and stored.

### Tests for User Story 3
- [x] T021 [P] [US3] Unit tests for RPE, RIR, and rest interval extraction in `tests/unit/test_gym_parser.py`

### Implementation for User Story 3
- [x] T022 [US3] Extend `src/services/gym_parser.py` with RPE patterns ("at RPE X", "felt like RPE X", "X reps in reserve") and rest duration patterns ("rest X minutes/seconds")
- [x] T023 [US3] Update set commit handling in `src/api/gym.py` to persist `rpe` and `rest_seconds` in `strength_sets`
- [x] T024 [P] [US3] Integration test for RPE and rest duration persistence in `tests/integration/test_gym_api.py`

**Checkpoint**: User Stories 1, 2, and 3 work independently and in combination.

---

## Phase 6: User Story 4 - Multi-Set or Multi-Exercise Batch Dictation (Priority: P3)

**Goal**: Parse compound sentences containing multiple distinct exercise clauses (e.g. "3 sets of 10 dumbbell lunges with 50s, followed by 3 sets of 15 calf raises") into ordered, discrete exercise groups.

**Independent Test**: Pass multi-exercise compound sentences into `POST /api/v1/gym/parse` and confirm discrete parsed set candidates are produced for each exercise without attribute mixing.

### Tests for User Story 4
- [x] T025 [P] [US4] Unit tests for multi-exercise compound sentence parsing in `tests/unit/test_gym_parser.py`

### Implementation for User Story 4
- [x] T026 [US4] Implement multi-clause sentence segmentation in `src/services/gym_parser.py` ("followed by", "then", "and then", ",") returning ordered `parsed_sets`
- [x] T027 [P] [US4] Integration test for multi-exercise batch dictation and atomic commit in `tests/integration/test_gym_api.py`

**Checkpoint**: All user stories (P1 through P3) are fully functional.

---

## Phase 7: Polish & Mobile Web UI Slice

**Purpose**: Mobile client interface, golden test suite execution, and end-to-end quickstart validation

- [x] T028 [P] Implement mobile-responsive Gym Mode web interface in `src/static/gym.html` with microphone button (iOS Web Speech dictation), staged card review, 1-tap Confirm, and inline edit controls
- [x] T029 Mount static directory and `/gym` HTML route in `src/main.py`
- [x] T030 [P] Execute complete golden test suite covering all 40+ spoken gym phrases in `tests/unit/test_gym_parser.py`
- [x] T031 Run end-to-end verification scenarios from `specs/002-gym-voice-logging/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001) — BLOCKS all user stories.
- **User Story 1 (Phase 3 - MVP)**: Depends on Foundational completion.
- **User Story 2 (Phase 4)**: Depends on Foundational and User Story 1 parser baseline.
- **User Story 3 (Phase 5)**: Depends on Foundational and User Story 1 parser baseline.
- **User Story 4 (Phase 6)**: Depends on Foundational and User Stories 1-3.
- **Polish (Phase 7)**: Depends on all user stories being complete.

### Parallel Opportunities
- Foundational models T003 (`strength_set.py`), T004 (`voice_log.py`), and T007 (`schemas/gym.py`) can run in parallel once T002 is created.
- Unit tests T009 and T010 can be developed in parallel with service implementations.
- US2 tests (T017), US3 tests (T021), and US4 tests (T025) can run in parallel before their respective service enhancements.
- T028 (Mobile UI) and T030 (Golden test suite) can run in parallel during the polish phase.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup (`rapidfuzz`)
2. Complete Phase 2: Foundational (Models, Migration, Seed Catalog, Schemas)
3. Complete Phase 3: User Story 1 (Compound lifts, `/gym/parse`, `/gym/sessions/{id}/sets`)
4. **STOP and VALIDATE**: Verify compound barbell lifts parse and save with 100% precision.

### Incremental Delivery
1. Foundation + US1 $\to$ Instant MVP for barbell/dumbbell strength training.
2. US2 $\to$ Adds bodyweight calisthenics with added/counter load isolation.
3. US3 $\to$ Adds RPE/RIR exertion and rest tracking for progressive overload.
4. US4 $\to$ Adds batch multi-exercise dictation.
5. Polish $\to$ Mobile web UI and golden test validation.
