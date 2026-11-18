# Implementation Plan: Unified Training Volume Modeling and Peak Performance Dashboard

**Branch**: `feature/003-volume-dashboard` | **Date**: 2026-11-17 | **Spec**: [specs/003-volume-dashboard/spec.md](spec.md)

**Input**: Feature specification from `specs/003-volume-dashboard/spec.md`

## Summary

Build the unified training volume modeling engine and interactive visual dashboard:
1. Aggregate cardiovascular endurance metrics (weekly mileage, Zone 2 duration and percentage, Concept2 erg meters/splits).
2. Aggregate resistance training metrics (effective working sets excluding warmups, total volume load, muscle group distribution, external calisthenic added load).
3. Compute deterministic Personal Records (PRs) including Epley estimated 1RM/5RM ($w \times (1 + r/30)$ for $r \le 10$) and endurance milestones (5k/10k, 500m/2k erg within $\pm 3\%$ tolerance).
4. Serve an interactive visual web dashboard at `/dashboard` powered by a local, self-hosted Chart.js bundle with rolling time-window filters (`7D`, `30D`, `90D`, `YTD`, `All`).

## Technical Context

**Language/Version**: Python 3.12 (backend), Modern ES6/HTML5 (dashboard frontend).

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic, Chart.js v4 (bundled locally in `src/static/vendor/chart.umd.js`).

**Storage**: PostgreSQL 16 (relational schema; indexed aggregations on `workout_sessions`, `strength_sets`, `strength_exercises`, plus `personal_records` cache/audit table).

**Testing**: `pytest`, `pytest-asyncio`, `httpx` (unit tests for volume formulas, Epley 1RM math, and PR detection; integration tests for `/analytics` endpoints and `/dashboard` rendering).

**Target Platform**: Self-hosted Docker container (FastAPI port 8001); desktop and mobile Safari/Chrome browsers.

**Project Type**: Monorepo service (FastAPI API + self-hosted frontend dashboard).

**Performance Goals**:
- Analytics aggregation queries execute in $< 25\text{ms}$ on PostgreSQL.
- API response latency $< 100\text{ms}$ for 90-day time window.
- Dashboard initial render $< 200\text{ms}$ with zero external CDN dependencies.

**Constraints**:
- Strictly self-hosted; zero cloud tracking or telemetry leaks.
- Warmup sets (`is_warmup = true`) must never inflate effective working set counts.
- Bodyweight calisthenic load must isolate external added resistance (+30 lbs) from barbell tonnage.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Design Status | Compliance Assessment |
|---|---|---|---|
| **I. Self-Hosted Architecture & Sovereignty** | Self-hosted data storage; no external analytics APIs or telemetry leaks. | **PASS** | Real-time SQL aggregations and local Chart.js bundle; zero third-party calls. |
| **II. Modular Ingestion & Source Isolation** | Analytics decoupled from raw ingestion payloads. | **PASS** | Operates strictly on canonical domain tables (`workout_sessions`, `strength_sets`). |
| **III. Multimodal Ergonomics & Robustness** | Responsive mobile iPhone presentation. | **PASS** | Mobile-optimized dashboard with touch-friendly filter pills and high-contrast charts. |
| **IV. Unified Volume Modeling & Peak Performance** | Exact mathematical volume aggregation, Zone 2 tracking, and deterministic PR detection across rolling windows. | **PASS** | Implements exact Epley 1RM, volume load, effective set filtering, and $\pm 3\%$ endurance milestone matching. |
| **V. Philosophy-Steered AI Coaching** | Provide structured metrics consumable by AI coaching analysis. | **PASS** | Unified analytics schemas (`VolumeSummary`, `PRSummary`) feed directly into Feature 4. |

## Project Structure

### Documentation (this feature)

```text
specs/003-volume-dashboard/
├── spec.md              # Feature specification with resolved clarifications
├── plan.md              # Architecture and implementation plan
├── research.md          # Phase 0 technical research & formula benchmark
├── data-model.md        # Phase 1 analytical aggregates and personal_records schema
├── quickstart.md        # Phase 1 verification scenarios and curl tests
├── contracts/           # Phase 1 OpenAPI 3.1 specification
│   └── api-analytics.yaml
└── checklists/
    └── requirements.md  # Specification quality validation checklist
```

### Source Code Layout

```text
src/
├── api/
│   ├── analytics.py            # Endpoints: /api/v1/analytics/summary, /cardio, /strength, /prs
│   └── router.py               # Mounts analytics router
├── models/
│   └── personal_record.py      # SQLAlchemy model: PersonalRecord
├── schemas/
│   └── analytics.py            # Pydantic schemas for volume summary, cardio, strength, PRs
├── services/
│   ├── analytics_service.py    # SQL volume aggregations, Zone 2 math, muscle group tallies
│   └── pr_detector.py          # Deterministic Epley 1RM math, milestone detection, PR ranking
├── static/
│   ├── dashboard.html          # Interactive visual dashboard
│   └── vendor/
│       └── chart.umd.js        # Self-hosted Chart.js v4 bundle (zero external CDN)
└── main.py                     # Mounts /dashboard route

tests/
├── unit/
│   ├── test_analytics_service.py # Unit tests for volume math, effective sets, and Zone 2 %
│   └── test_pr_detector.py       # Unit tests for Epley 1RM, rep cap, and endurance milestones
└── integration/
    └── test_analytics_api.py     # End-to-end API tests for /analytics endpoints and /dashboard
```

## Complexity Tracking

*No architectural violations detected. No unjustified complexity introduced.*
