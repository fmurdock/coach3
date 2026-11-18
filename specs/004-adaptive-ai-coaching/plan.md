# Implementation Plan: Adaptive AI Coaching Engine with Dual-Engine Architecture

**Branch**: `feature/004-adaptive-ai-coaching` | **Date**: 2026-11-18 | **Spec**: [specs/004-adaptive-ai-coaching/spec.md](spec.md)

**Input**: Feature specification from `specs/004-adaptive-ai-coaching/spec.md`

---

## Summary

Build the Adaptive AI Coaching Engine fulfilling Constitution Principle V and Principle I:
1. **Dual-Engine Inference Architecture**: Support both Google Gemini API (cloud, high reasoning) and self-hosted `llama.cpp` server (local homelab inference via OpenAI-compatible `/v1/chat/completions`) using unified async HTTP clients via `httpx`.
2. **Privacy Scrubbing & Data Sovereignty**: Strip 100% of PII and GPS route coordinates before cloud dispatch.
3. **Philosophy Steering Engine**: Manage user training philosophies with programmatic guardrails (Zone 2 %, volume ramp limits, max RPE) and manual context document loading (notes, book excerpts, injury history, movement exclusions).
4. **Analysis & Planning Modes**: Provide retrospective workout critique (Analysis Mode) and periodized 1–2 week forward microcycle schedule generation (Planning Mode).
5. **Interactive Web Coaching Interface**: Serve mobile-optimized `/coach` UI for provider management, philosophy tuning, critique reading, and schedule calendar tracking.

---

## Technical Context

**Language/Version**: Python 3.12 (backend), Modern HTML5/ES6 (frontend).

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic, `httpx` (unified async REST client for Gemini and `llama.cpp`), `cryptography` (Fernet encryption for stored Gemini API keys).

**Storage**: PostgreSQL 16 (new tables: `llm_provider_configs`, `coaching_philosophies`, `coaching_critiques`, `training_schedule_plans`, `scheduled_workouts`).

**Testing**: `pytest`, `pytest-asyncio`, `httpx` (offline mock transports for LLM provider adapters, unit tests for privacy scrubbing, philosophy validation, and periodization boundaries).

**Target Platform**: Self-hosted Docker container (FastAPI port 8001); desktop and mobile Safari/Chrome browsers.

**Project Type**: Monorepo service (FastAPI API + self-hosted coaching frontend).

**Performance Goals**:
- Critique generation latency $< 4\text{s}$ on Gemini and $< 8\text{s}$ on local homelab `llama.cpp`.
- Provider health check response $< 200\text{ms}$.
- Web coaching interface render $< 150\text{ms}$ with zero external CDN dependencies.

**Constraints**:
- Strictly self-hosted data storage.
- 100% PII and raw GPS route data stripped from external cloud prompts (Constitution Principle I).
- Manual provider failover with descriptive diagnostics (no unexpected cloud billing).
- Forward plans must strictly enforce the $\le 10\%$ weekly volume progression ceiling.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Design Status | Compliance Assessment |
|---|---|---|---|
| **I. Self-Hosted Architecture & Sovereignty** | Self-hosted storage; opt-in cloud API; privacy scrubbing; local model support. | **PASS** | Native local `llama.cpp` support; Fernet encrypted keys; strict PII/GPS route stripping on Gemini calls. |
| **II. Modular Ingestion & Source Isolation** | Coaching decoupled from raw ingestion payloads. | **PASS** | Operates exclusively on canonical domain tables (`workout_sessions`, `strength_sets`, `personal_records`). |
| **III. Multimodal Ergonomics & Robustness** | Responsive mobile interface; resilient to network glitches. | **PASS** | Clean `/coach` mobile UI with status indicators, graceful error banners, and manual provider selection. |
| **IV. Unified Volume Modeling & Peak Performance** | Consumes normalized metrics across endurance and strength. | **PASS** | Integrates Feature 003 volume loads, Zone 2 percentages, and Epley 1RM PRs directly into analysis context. |
| **V. Philosophy-Steered, Adaptive AI Coaching** | Decoupled philosophies; planning and analysis modes. | **PASS** | Full implementation of Analysis Mode (critique) and Planning Mode (schedules) steered by `CoachingPhilosophy`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/004-adaptive-ai-coaching/
├── spec.md              # Feature specification with resolved clarifications
├── plan.md              # Architecture and implementation plan
├── research.md          # Phase 0 technical research & provider analysis
├── data-model.md        # Phase 1 data model & table specifications
├── quickstart.md        # Phase 1 verification scenarios and curl tests
├── contracts/           # Phase 1 OpenAPI 3.1 specification
│   └── api-coaching.yaml
└── checklists/
    └── requirements.md  # Specification quality validation checklist
```

### Source Code Layout

```text
src/
├── api/
│   ├── coaching.py             # Endpoints: /providers, /philosophies, /analyze, /plan
│   └── router.py               # Mounts coaching router
├── core/
│   └── privacy.py              # PII and GPS route scrubbing service
├── models/
│   ├── coaching.py             # SQLAlchemy models: LLMProviderConfig, CoachingPhilosophy,
│   │                           # CoachingCritique, TrainingSchedulePlan, ScheduledWorkout
│   └── __init__.py             # Exports coaching models
├── schemas/
│   └── coaching.py             # Pydantic v2 schemas for requests, responses, and LLM structured outputs
├── services/
│   ├── llm_client.py           # Abstract BaseLLMClient, GeminiClient, LlamaCppClient
│   ├── coaching_service.py     # Prompt assembly, analysis engine, periodization schedule generator
│   └── philosophy_service.py   # Philosophy management and validation
├── static/
│   └── coach.html              # Responsive coaching UI
└── main.py                     # Mounts /coach route

alembic/versions/
└── 004_coaching_schema.py      # Migration creating 5 coaching tables and seed philosophies

tests/
├── unit/
│   ├── test_llm_client.py      # Unit tests for Gemini and llama.cpp HTTP clients (mocked)
│   ├── test_privacy.py         # Unit tests verifying PII and GPS stripping
│   └── test_coaching_service.py# Unit tests for prompt assembly, philosophy guardrails, plan parsing
└── integration/
    └── test_coaching_api.py    # Integration tests for /coaching endpoints and /coach UI
```

---

## Complexity Tracking

*No architectural violations detected. No unjustified complexity introduced.*
