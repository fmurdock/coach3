# Research & Architectural Decisions: 008-remediation2

**Feature**: [spec.md](spec.md) | **Date**: 2026-11-26

## 1. Lazy Gym Session Creation (`FR-001`–`FR-004`)

- **Decision**: Make `GET /api/v1/gym/sessions/active` strictly read-only (returning `WorkoutSessionResponse | None`, i.e., `null` when no active `< 4h` strength session exists), add `POST /api/v1/gym/sets` (with optional `session_id` in `CommitSetsRequest`) to lazily find or create the strength session on first commit, and delete empty `coach3_gym` sessions in `DELETE /api/v1/gym/sets/{set_id}` when the last set is removed.
- **Rationale**: Filtering 0-set sessions out only on `/api/v1/workouts` would leave phantom rows in `workout_sessions` and `export`. Lazy materialization keeps the database clean, lets offline-queued sets sync even when no session existed at queue time, and uses `ZoneInfo(user.timezone or "UTC")` for accurate local-date session titles.
- **Alternatives considered**:
  - *Read-time filtering (`HAVING count(sets) > 0`)*: Rejected because phantom rows still accumulate in `workout_sessions` and ZIP exports.
  - *Explicit "Start Workout" button*: Rejected because it violates Constitution Principle III (minimal-friction mobile logging).

## 2. Cardio & Lifting Dashboard Tabs (`FR-005`, `FR-006`)

- **Decision**: Partition [dashboard.html](file:///Users/frankmurdock/coach3/src/static/dashboard.html) and [dashboard.js](file:///Users/frankmurdock/coach3/src/static/js/dashboard.js) into two top-level modality tabs (**Cardio** and **Lifting**), keeping the shared time-window filter bar and Sync button above the tabs.
  - **Cardio tab**: Cardio KPIs (Total Cardio Duration, Zone 2 Cardio, VO2 Max Stimulus, Running, Erg Work), Zone 2 & VO2 Max macro charts, Heart Rate Zone Distribution chart, Cardio PRs, and Cardio Workouts table (`outdoor_run`, `indoor_row`, `erg_bike`).
  - **Lifting tab**: Lifting KPIs (Lifting Sessions, Working Sets, Total Volume, Top Est. 1RM), Resistance Volume table (Push/Pull/Legs/Abs), Strength PRs, and Lifting Workouts table (`strength`).
- **Rationale**: Separating modalities eliminates a long mixed scroll view while preserving a single shared window state (`7d`, `30d`, `90d`, `ytd`, `all`, custom dates). Switching tabs clears any expanded workout detail drawer so no stale drawer remains open across tabs.
- **Alternatives considered**:
  - *Separate `/cardio` and `/lifting` routes*: Rejected to avoid duplicating navbar links and splitting the shared window/sync state.

## 3. Calm, User-Friendly, Professional Visual Design (`FR-007`)

- **Decision**: Refine [common.css](file:///Users/frankmurdock/coach3/src/static/css/common.css) and page-level styles across `dashboard.html`, `gym.html`, `coach.html`, `config.html`, and `login.html` to adopt a restrained, high-readability slate palette (`#0f172a` / `#1e293b` surfaces, `#334155` subtle 1px borders, muted `#3b82f6` primary accent, `#10b981`/`#f59e0b`/`#ef4444` semantic statuses), removing heavy neon glows (`box-shadow` glows, radial gradients on route cards, flashy hover transforms) and tightening typographic hierarchy, padding, and table/card alignment.
- **Rationale**: Keeping all styling in `common.css` + thin CSS variables/rules preserves the CSP (`script-src 'self'`, clean dark/neutral surfaces) and improves legibility across desktop and mobile without altering any JS behavior.
- **Alternatives considered**:
  - *Full light-mode rewrite or external CSS framework*: Rejected to avoid breaking existing chart palettes and adding external build/CDN dependencies.

## 4. LLM Server Connections & Prompt/Output Verification Test (`FR-008`, `FR-009`)

- **Decision**: Harden `LlamaCppClient` and `GeminiClient` in [llm_client.py](file:///Users/frankmurdock/coach3/src/services/llm_client.py):
  1. **Endpoint URL normalization (`LlamaCppClient`)**: Handle base URLs ending in `/chat/completions`, `/v1`, or bare host:port cleanly without double-appending `/v1/chat/completions`.
  2. **Docker host-loopback ergonomics**: When running inside a container (`/.dockerenv` exists) and `LlamaCppClient` fails to connect to `localhost`/`127.0.0.1`, surface a clear actionable hint recommending `host.docker.internal` (or LAN IP) instead of an opaque connection error.
  3. **Reliable health/connection test (`test_connection`)**:
     - Use a short fitness-relevant prompt (`"In one short sentence, explain Zone 2 cardio."`) without forcing `response_format` / `responseMimeType: "application/json"` on the health check (which some llama.cpp/OpenAI-compatible servers reject with `400`/`422`), and increase Gemini `maxOutputTokens` from `20` to `128` so thinking models (e.g., `gemini-2.5-flash`) don't exhaust tokens before emitting text.
     - Parse and verify a non-empty text response from `choices[0].message.content` (llama.cpp) or `candidates[0].content.parts[0].text` (Gemini), returning `status="error"` if the server returns `200` with empty output.
  4. **Structured JSON resilience (`generate_structured`)**: Strip markdown code fences (```` ```json ... ``` ````) if a local server wraps its JSON output, and fallback cleanly if `response_format` returns `400`/`422` on a local server.
  5. **Automated prompt-and-output test**: Add deterministic unit/integration tests in `tests/unit/test_llm_client.py` (plus an optional `LIVE_LLM_TEST_URL` / `LIVE_GEMINI_API_KEY` live smoke test) that send a short fitness-relevant prompt and assert a non-empty output is returned.
- **Rationale**: Addresses every real failure mode observed with local `llama.cpp` servers and Gemini 2.5 Flash while keeping standard test suites 100% deterministic offline.
- **Alternatives considered**:
  - *Sending `GET /health` or `GET /v1/models` instead of a prompt*: Rejected because `GET /models` can succeed even when inference/model loading fails, and the user explicitly requested a test that sends a short relevant prompt and expects an output.
