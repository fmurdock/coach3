---
description: "Dependency-ordered implementation tasks for 008-remediation2 (lazy gym sessions, LLM connection fixes + prompt test, Cardio/Lifting dashboard tabs, calm professional UI)"
---

# Tasks: Gym Session Hygiene, Dashboard Cardio/Lifting Tabs, Professional UI Polish, and LLM Connection Verification

**Input**: Design documents from `/specs/008-remediation2/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/api-008.yaml](contracts/api-008.yaml), [quickstart.md](quickstart.md)

**Tests**: Included for User Story 1 (lazy gym session creation & cleanup) and User Story 2 (LLM prompt-and-output verification test per `FR-009`), plus full `ruff`/`mypy`/`pytest` verification in the Polish phase.

**Organization**: Tasks are grouped by user story (`US1`–`US4`) in priority order (`P1 → P2`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story mapping (`[US1]`–`[US4]`) — omitted in Setup and Polish phases
- Exact repository file paths are included in every task

---

## Phase 1: Setup

**Purpose**: Verify baseline test suite and prepare feature workspace.

- [X] T001 Verify baseline `.venv/bin/pytest -W default -q` and `.venv/bin/ruff check src tests` pass before `008-remediation2` edits in `tests/`

---

## Phase 2: User Story 1 - Zero-Blank-Workout Gym Logging (Priority: P1) 🎯 MVP

**Goal**: Prevent `/gym` page loads from creating empty `0`-set `WorkoutSession` rows; lazily create the session on first set commit (with athlete local-date title), support offline queue flushing without a pre-existing `session_id`, and delete empty `coach3_gym` sessions when the last set is deleted.

**Independent Test**: Call `GET /api/v1/gym/sessions/active` on an empty DB and verify `null` is returned with zero `WorkoutSession` rows created; commit sets via `POST /api/v1/gym/sets` and verify session creation + reuse + idempotency; delete the only set and verify the empty session is removed.

### Tests for User Story 1

- [X] T002 [US1] Update `test_get_active_strength_session` and add integration tests for lazy `POST /api/v1/gym/sets` creation, local-timezone session title, `submission_key` idempotency, and empty-session deletion on last-set `DELETE /api/v1/gym/sets/{id}` in `tests/integration/test_gym_api.py`

### Implementation for User Story 1

- [X] T003 [P] [US1] Add optional `session_id: uuid.UUID | None = None` field to `CommitSetsRequest` in `src/schemas/gym.py`
- [X] T004 [US1] Make `GET /api/v1/gym/sessions/active` read-only (`WorkoutSessionResponse | None`, returning `None` when no `< 4h` strength session exists), extract `_commit_sets_impl()`, add `POST /api/v1/gym/sets` with lazy `ZoneInfo(user.timezone or "UTC")` session creation, and auto-delete empty `coach3_gym` sessions in `DELETE /api/v1/gym/sets/{set_id}` in `src/api/gym.py`
- [X] T005 [US1] Update `initSession()`, `btnConfirm`, `flushOfflineQueue()`, and `deleteSet()` to handle `null` active session (`Ready to Log`), post to `/api/v1/gym/sets`, update `activeSessionId` from `committedSets[0].workout_session_id`, and reset `activeSessionId` when the last set is deleted in `src/static/js/gym.js`

**Checkpoint**: User Story 1 is complete and independently verifiable — opening `/gym` creates zero blank workouts.

---

## Phase 3: User Story 2 - Reliable AI Server Connections & Live Prompt Verification (Priority: P1)

**Goal**: Fix cloud (Gemini) and local (`llama.cpp`) LLM server connection handling (endpoint URL normalization, ping token budget & `response_format` compatibility, non-empty output validation, markdown fence stripping, Docker `localhost` hint) and add an automated test that sends a short fitness-relevant prompt and asserts a non-empty output.

**Independent Test**: Run `tests/unit/test_llm_client.py` and `tests/integration/test_coaching_api.py` verifying short fitness prompt execution returns non-empty output and invalid/unreachable states surface clear diagnostics.

### Tests for User Story 2

- [X] T006 [P] [US2] Add unit tests in `tests/unit/test_llm_client.py` sending a short fitness-relevant prompt (`"In one short sentence, explain Zone 2 cardio."`) through `GeminiClient` and `LlamaCppClient` (verifying non-empty output), plus tests for `/chat/completions` URL normalization, empty-output error detection, `response_format` fallback, markdown fence stripping, and optional live server smoke test (`LIVE_LLM_TEST_URL`)
- [X] T007 [P] [US2] Add integration test for `POST /api/v1/coaching/providers/{provider_id}/test` verifying short-prompt live health verification and clear `unreachable` / `invalid_credentials` responses in `tests/integration/test_coaching_api.py`

### Implementation for User Story 2

- [X] T008 [US2] Remediate `LlamaCppClient` and `GeminiClient` in `src/services/llm_client.py` to normalize `/v1` and `/chat/completions` URLs cleanly, use a short fitness prompt without forcing `response_format` on `test_connection()`, raise Gemini ping `maxOutputTokens` to `128`, verify non-empty model text output on health checks, strip markdown JSON fences in `generate_structured()`, fallback cleanly if a local server rejects `response_format`, and include a Docker `host.docker.internal` hint when `localhost`/`127.0.0.1` is unreachable inside a container
- [X] T009 [US2] Ensure `POST /api/v1/coaching/providers/{provider_id}/test` and `POST /api/v1/coaching/providers` surface clear validation/connection diagnostics cleanly in `src/api/coaching.py`

**Checkpoint**: User Story 2 is complete and independently verifiable — LLM connections and prompt-output verification tests pass.

---

## Phase 4: User Story 3 - Dedicated Cardio and Lifting Dashboard Tabs (Priority: P2)

**Goal**: Separate the Dashboard into distinct **Cardio** and **Lifting** tabs so endurance KPIs, Zone 2 / VO2 Max / HR Zone charts, cardio PRs, and cardio workout history are separated from lifting KPIs, Resistance Volume (Push/Pull/Legs/Abs), strength PRs, and lifting workout history while preserving the shared time-window filter.

**Independent Test**: Open `/dashboard`, switch between **Cardio** and **Lifting** tabs across time windows (`7d`, `30d`, `all`, custom), and verify each tab displays only its modality's metrics, charts, PRs, and workout rows.

### Implementation for User Story 3

- [X] T010 [US3] Restructure `src/static/dashboard.html` to add accessible **Cardio** and **Lifting** tab buttons (`role="tablist"`, `role="tab"`) below the shared filter bar, grouping Cardio KPIs/charts/PRs/workouts into `#tab-panel-cardio` and Lifting KPIs/Resistance table/PRs/workouts into `#tab-panel-lifting`
- [X] T011 [US3] Update `src/static/js/dashboard.js` to manage `activeDashboardTab` (`'cardio'` | `'lifting'`), compute/render modality-specific KPIs and PR lists, filter workout history by cardio (`outdoor_run`, `indoor_row`, `erg_bike`) vs lifting (`strength`), close any expanded detail drawer on tab switch, and preserve the shared time-window filter across tabs

**Checkpoint**: User Story 3 is complete and independently verifiable — Cardio and Lifting tabs work cleanly with shared time-window filters.

---

## Phase 5: User Story 4 - Calm, User-Friendly, and Professional Visual Design (Priority: P2)

**Goal**: Replace flashy neon gradients, heavy glow shadows, and jarring accents across all web pages with a calm, restrained, high-readability, professional slate aesthetic and clean spacing/typography.

**Independent Test**: Inspect `/dashboard`, `/gym`, `/coach`, `/config`, and `/login` on desktop and mobile viewports and run `tests/integration/test_static_routes.py`.

### Implementation for User Story 4

- [X] T012 [P] [US4] Refine color tokens, navbar, badges, buttons, inputs, and toast styles in `src/static/css/common.css` to use a calm, restrained slate palette (`#0f172a` background, `#1e293b` card surface, `#334155` subtle 1px borders, muted `#3b82f6` primary accent), removing heavy drop-shadow glows and flashy contrast
- [X] T013 [P] [US4] Update page-specific styles in `src/static/dashboard.html`, `src/static/gym.html`, `src/static/coach.html`, `src/static/config.html`, and `src/static/login.html` to remove radial gradients, heavy neon borders/glows, and noisy accents while maintaining crisp typographic hierarchy, table readability, and mobile ergonomics

**Checkpoint**: User Story 4 is complete — all 5 web interfaces share a calm, user-friendly, professional design.

---

## Phase 6: Polish & Final Verification

**Purpose**: Static analysis, type checking, full test suite, and live container verification.

- [X] T014 Run `.venv/bin/ruff check src tests` and `.venv/bin/mypy src` and resolve any lint, security (`S`), or type findings
- [X] T015 Run `.venv/bin/pytest -W default -v` confirming all unit and integration tests pass with zero deprecation warnings
- [X] T016 Clean up any legacy empty `0`-set `coach3_gym` row in `coach3_dev`, rebuild and start `docker compose up --build -d app`, and execute manual end-to-end checks from `specs/008-remediation2/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Start immediately.
- **Phase 2 (`US1` — P1)**: Depends on Phase 1.
- **Phase 3 (`US2` — P1)**: Depends on Phase 1 (independent of `US1`, can run in parallel).
- **Phase 4 (`US3` — P2)**: Depends on Phase 1 (independent of `US1` and `US2`).
- **Phase 5 (`US4` — P2)**: `T012` (`common.css`) runs before or alongside `T013`; coordinate `dashboard.html` edits after `T010` (`US3`) to avoid merge conflicts.
- **Phase 6 (Polish)**: Depends on all user stories (`US1`–`US4`) being complete.

### Parallel Opportunities

- `US1` backend (`T003`, `T004`) and `US2` (`T006`, `T007`, `T008`, `T009`) touch completely separate files and can be implemented in parallel.
- Within `US4`, `T012` (`common.css`) and `T013` (HTML shells) can run in parallel once `T010` (`dashboard.html`) is done.

---

## Implementation Strategy

### MVP First (User Stories 1 & 2)

1. Complete Phase 1 (`T001`).
2. Complete Phase 2 (`US1`: lazy gym session creation + empty-session cleanup) and Phase 3 (`US2`: LLM server connection fixes + prompt-output test).
3. Complete Phase 4 (`US3`: Cardio & Lifting Dashboard tabs) and Phase 5 (`US4`: calm, professional UI polish).
4. Complete Phase 6 (`T014`–`T016`): `ruff`, `mypy`, `pytest`, and live Docker container verification.
