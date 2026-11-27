
# Implementation Plan: Gym Session Hygiene, Dashboard Cardio/Lifting Tabs, Professional UI Polish, and LLM Connection Verification

**Branch**: `008-remediation2` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-remediation2/spec.md`

## Summary

Eliminate phantom blank 0-set gym workouts via lazy session materialization (`GET /api/v1/gym/sessions/active` read-only + `POST /api/v1/gym/sets` + empty-session cleanup on last-set deletion), separate the Dashboard into **Cardio** and **Lifting** tabs sharing a single time-window filter, refine the UI styling across all pages to be calm, user-friendly, and professional, and fix cloud/local LLM server connections with an automated prompt-and-output verification test.

## Technical Context

**Language/Version**: Python 3.12+ (container `python:3.12-slim`, local `.venv` Python 3.15)  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, httpx, Vanilla HTML/CSS/JS + Chart.js (`/static/vendor/chart.umd.js`)  
**Storage**: PostgreSQL 16 (`coach3_dev` in Docker) & SQLite (`aiosqlite` for fast test suite) — no schema migration needed  
**Testing**: `.venv/bin/pytest -W default -v`, `.venv/bin/ruff check src tests`, `.venv/bin/mypy src`  
**Target Platform**: Docker Compose self-hosted deployment + macOS/iOS browsers  
**Project Type**: Single-repository FastAPI + static frontend web application  
**Performance Goals**: Instant client-side Cardio/Lifting tab switching; zero unnecessary DB writes on `/gym` page load  
**Constraints**: Strict `script-src 'self'` CSP, zero external CSS/JS CDNs, single-athlete privacy scrubbing preserved

## Constitution Check

*GATE: Evaluated pre-research and re-evaluated post-design.*

| Principle / Standard | Status | Notes |
| :--- | :---: | :--- |
| **I. Self-Hosted Architecture & Data Sovereignty** | PASS | No phantom sessions pollute exports; local LLM connections remain self-hosted. |
| **II. Modular Ingestion & Source Isolation** | PASS | `coach3_gym` remains isolated from Polar/Concept2 adapters. |
| **III. Multimodal Ergonomics & Natural Language Robustness** | PASS | Zero-friction logging without a "Start Workout" button; offline queue works with `session_id=null`. |
| **IV. Unified Volume Modeling & Peak Performance Analytics** | PASS | Cardio & Lifting tabs separate presentation without altering canonical 1RM or timezone math. |
| **V. Philosophy-Steered, Adaptive AI Coaching** | PASS | Fixes Gemini/llama.cpp connections and adds prompt-and-output verification test. |
| **Development Workflow & Quality Standards** | PASS | Full `ruff`, `mypy`, and `pytest` verification included. |

## Project Structure

### Documentation (this feature)

```text
specs/008-remediation2/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api-008.yaml
├── checklists/
│   └── requirements.md
└── tasks.md              # Created next by /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── schemas/gym.py        # MODIFIED: optional session_id on CommitSetsRequest
├── api/gym.py            # MODIFIED: read-only GET /sessions/active, new POST /sets, local-tz title, cleanup empty session on DELETE
├── services/llm_client.py# MODIFIED: URL normalization, non-JSON ping + higher token budget, non-empty output check, fence stripping, Docker localhost hint
└── static/
    ├── css/common.css    # MODIFIED: calm, restrained, professional slate palette & surface tokens
    ├── dashboard.html    # MODIFIED: Cardio & Lifting tabs + refined surface/table/chart styling
    ├── gym.html          # MODIFIED: refined surface/card styling
    ├── coach.html        # MODIFIED: refined surface/card styling
    ├── config.html       # MODIFIED: refined surface/card styling
    ├── login.html        # MODIFIED: refined surface/card styling
    └── js/
        ├── gym.js        # MODIFIED: handle null active session, POST /api/v1/gym/sets, reset on last-set delete
        └── dashboard.js  # MODIFIED: Cardio/Lifting tab state, modality-filtered rendering & history

tests/
├── unit/test_llm_client.py       # MODIFIED: prompt-and-output tests for Gemini & llama.cpp + URL/fence/empty-output edge cases
└── integration/
    ├── test_gym_api.py           # MODIFIED: read-only GET /sessions/active, lazy POST /sets, last-set cleanup
    └── test_coaching_api.py      # MODIFIED: provider /test endpoint prompt-and-output integration test
```

**Structure Decision**: Preserve the existing `src/` + `tests/` layout with no database migrations required.

## Complexity Tracking

No Constitution violations requiring exceptions.
