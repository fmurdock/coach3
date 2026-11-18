# Implementation Plan: Gym Mode Natural Language Workout Logging

**Branch**: `feature/002-gym-voice-logging` | **Date**: 2026-11-17 | **Spec**: [specs/002-gym-voice-logging/spec.md](spec.md)

**Input**: Feature specification from `specs/002-gym-voice-logging/spec.md`

## Summary

Build Gym Mode natural language workout logging for iPhone mobile users: client-side speech dictation submits raw text transcripts to a deterministic, high-performance grammar and fuzzy alias parser in Python. The system identifies compound barbell lifts, dumbbell exercises, and bodyweight calisthenics with added external resistance (weight belts/vests), plate math ("two plates" $\to$ 225 lbs), and RPE exertion. Extracted sets are presented as an immediate staged review card on mobile before atomic, idempotent persistence to PostgreSQL `strength_sets` and `voice_transcription_logs`.

## Technical Context

**Language/Version**: Python 3.12 (backend service), Modern ES6/HTML5 (mobile web client).

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncio + asyncpg), `rapidfuzz>=3.6.0`, Alembic.

**Storage**: PostgreSQL 16 (relational schema with UUID primary keys, JSONB audit storage, and unique idempotency keys).

**Testing**: `pytest`, `pytest-asyncio`, `httpx` (unit testing for grammar rules, fuzzy alias matching golden test suite with 40+ spoken phrasings, and API integration tests).

**Target Platform**: Self-hosted Docker container (Linux x86_64 / arm64) running FastAPI service on port 8001; mobile Safari / Web Speech client on iPhone.

**Project Type**: Monorepo service (FastAPI backend + mobile-optimized HTML/JS UI slice).

**Performance Goals**:
- Natural language parsing latency $< 10\text{ms}$ per utterance on CPU.
- Staged preview returned to mobile client in $< 150\text{ms}$ network round-trip.
- Zero external LLM token overhead or cloud dependency.

**Constraints**:
- Must run completely self-hosted with no mandatory external APIs.
- Strict pre-defined exercise dictionary with alias normalization.
- 100% distinction between base bodyweight and added/counter load.

**Scale/Scope**: Single-user self-hosted or family homelab deployment; thousands of lifetime sets with millisecond retrieval.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Design Status | Compliance Assessment |
|---|---|---|---|
| **I. Self-Hosted Architecture & Sovereignty** | Self-hosted data storage; no biometric or voice leaks to third-party APIs. | **PASS** | Parsing and alias matching run entirely in local Python runtime. No cloud STT or external LLM API used. |
| **II. Modular Ingestion & Source Isolation** | Gym voice logging decoupled as a dedicated ingestion adapter/service. | **PASS** | Handled in `src/services/gym_parser.py` and `src/api/gym.py`, isolated from Polar/Concept2 endurance adapters. |
| **III. Multimodal Ergonomics & Robustness** | Mobile-first iPhone voice entry, noise tolerance, plate math, explicit confirmation. | **PASS** | Client-side dictation, multi-pass regex grammar with colloquial slang ("two plates"), and staged confirmation card. |
| **IV. Unified Volume Modeling** | Distinct tracking of sets, reps, barbell load, and added bodyweight load. | **PASS** | Schema provides `is_bodyweight`, `weight`, and `added_weight` columns for downstream 1RM/volume modeling. |
| **V. Philosophy-Steered AI Coaching** | Retain raw transcripts and RPE data for training adherence analysis. | **PASS** | `voice_transcription_logs` and `rpe` attributes on `strength_sets` preserve full context for Feature 4. |

## Project Structure

### Documentation (this feature)

```text
specs/002-gym-voice-logging/
├── spec.md              # Feature specification with resolved clarifications
├── plan.md              # This architecture and implementation plan
├── research.md          # Phase 0 technical research & parser benchmark strategy
├── data-model.md        # Phase 1 relational schema and entity definitions
├── quickstart.md        # Phase 1 verification scenarios and curl tests
├── contracts/           # Phase 1 OpenAPI 3.1 specification
│   └── api-voice-logging.yaml
└── checklists/
    └── requirements.md  # Specification quality validation checklist
```

### Source Code Layout

```text
src/
├── api/
│   ├── gym.py                  # Endpoints: /api/v1/gym/parse, /exercises, /sessions/{id}/sets
│   └── router.py               # Mounts gym router into api_router
├── models/
│   ├── exercise.py             # SQLAlchemy models: StrengthExercise, ExerciseAlias
│   ├── strength_set.py         # SQLAlchemy model: StrengthSet
│   └── voice_log.py            # SQLAlchemy model: VoiceTranscriptionLog
├── schemas/
│   └── gym.py                  # Pydantic models for parse requests, staged cards, and set commits
├── services/
│   ├── exercise_catalog.py     # Canonical taxonomy, alias caching, RapidFuzz matcher
│   └── gym_parser.py           # Deterministic grammar, regex extractors, plate math, RPE
└── scripts/
    └── seed_exercises.py       # Seeds 120+ standard exercises and synonyms

tests/
├── unit/
│   ├── test_gym_parser.py      # Golden test suite for spoken gym phrasings & edge cases
│   └── test_exercise_catalog.py# Taxonomy search, alias resolution, and fuzzy matching
└── integration/
    └── test_gym_api.py         # End-to-end API tests for parse, stage, and atomic commit
```

## Complexity Tracking

*No architectural violations detected. No unjustified complexity introduced.*
