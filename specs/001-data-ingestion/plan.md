# Implementation Plan: Core Data Ingestion & Telemetry Models

**Branch**: `001-data-ingestion` | **Date**: 2026-11-17 | **Spec**: [spec.md](file:///Users/frankmurdock/coach3/specs/001-data-ingestion/spec.md)

**Input**: Feature specification from `specs/001-data-ingestion/spec.md`

## Summary

Build the foundational self-hosted ingestion architecture and canonical relational telemetry store for Coach3. This feature provides modular ingestion adapters for Polar AccessLink (outdoor running) and Concept2 Logbook API (indoor rower and erg bike), normalizes cardiovascular and erg metrics into canonical entities, calculates Zone 1–5 durations locally from user heart rate profiles, stores full GPS route points and interval splits, and executes idempotent background synchronization on a fixed 60-minute schedule.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncio with `asyncpg`), Alembic, APScheduler, `httpx`, `cryptography` (Fernet)  
**Storage**: PostgreSQL 16 (relational schema with B-tree & composite indexing; Docker Compose managed)  
**Testing**: `pytest`, `pytest-asyncio`, `pytest-mock`, `httpx` TestClient  
**Target Platform**: Self-hosted Linux/macOS host via Docker & Docker Compose  
**Project Type**: Containerized backend web service (REST API + asynchronous background ingestion worker)  
**Performance Goals**: Workout ingestion processing <2s per 60-min session; API response <100ms for workout listing and telemetry queries  
**Constraints**: Fully self-hosted; credentials encrypted at rest; zero telemetry leaks to unvetted external services; idempotent sync (0 duplicate workouts)  
**Scale/Scope**: Multi-year athlete history (thousands of historical workouts, millions of telemetry data points)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- [x] **Principle I: Self-Hosted Architecture & Data Sovereignty**  
  *Verification*: Database is PostgreSQL running in local container. External tokens encrypted with local key. No external telemetry leakage.
- [x] **Principle II: Modular Ingestion & Source Isolation**  
  *Verification*: Polar and Concept2 adapters are isolated in `src/adapters/`. External payloads map to domain events via canonical schemas. Idempotency enforced via composite unique constraints `(provider, external_id)`.
- [x] **Principle III: Multimodal Ergonomics & Natural Language Robustness**  
  *Verification*: Ingestion models are decoupled and ready to accept future voice/gym inputs without breaking endurance schemas.
- [x] **Principle IV: Unified Volume Modeling & Peak Performance Analytics**  
  *Verification*: Canonical `WorkoutSession` models both running and erg workouts. Zone 2 cardio duration is calculated uniformly by Coach3 using the user's HR profile. Full GPS points and interval splits are stored.
- [x] **Principle V: Philosophy-Steered, Adaptive AI Coaching**  
  *Verification*: Domain models maintain queryable volume and metric aggregates necessary to feed upcoming planning and analysis features.
- [x] **Technical & Quality Standards**  
  *Verification*: Docker Compose deployment model; contract and unit test suite with mock API fixtures.

## Project Structure

### Documentation (this feature)

```text
specs/001-data-ingestion/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this document)
├── research.md          # Phase 0 architectural decisions & technical context
├── data-model.md        # Phase 1 ERD and table definitions
├── quickstart.md        # Phase 1 runnable validation guide
├── contracts/           # Phase 1 API and adapter interface contracts
│   └── api-ingestion.yaml
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code Layout

```text
src/
├── adapters/
│   ├── base.py                 # Abstract Base Ingestion Adapter
│   ├── polar.py                # Polar AccessLink API client & data mapper
│   └── concept2.py             # Concept2 Logbook API client & data mapper
├── api/
│   ├── router.py               # Combined API v1 router
│   ├── integrations.py         # Endpoints for account linking & on-demand sync
│   ├── workouts.py             # Endpoints for workout sessions & telemetry
│   └── profile.py              # Endpoints for user HR zone profile
├── core/
│   ├── config.py               # Environment variables & application settings (pydantic-settings)
│   ├── database.py             # Async SQLAlchemy engine & session factory
│   ├── security.py             # Fernet encryption/decryption utilities
│   └── scheduler.py            # APScheduler setup for 60-min recurring sync
├── models/
│   ├── base.py                 # DeclarativeBase with common timestamp mixins
│   ├── user.py                 # User & UserHeartRateProfile models
│   ├── integration.py          # IntegrationAccount & SyncAuditLog models
│   ├── workout.py              # WorkoutSession model
│   └── telemetry.py            # HeartRateSample, GPSRoutePoint, WorkoutSplit models
├── schemas/
│   ├── integration.py          # Pydantic schemas for integrations & sync logs
│   ├── workout.py              # Pydantic schemas for workout summaries & detail
│   └── profile.py              # Pydantic schemas for HR profile & zones
├── services/
│   ├── ingestion.py            # Ingestion orchestration & transaction coordinator
│   ├── zone_calculator.py      # Heart rate zone duration calculator
│   └── sync_service.py         # Sync job dispatcher & backfill pagination manager
└── main.py                     # FastAPI application factory & lifecycle events

tests/
├── conftest.py                 # Test database fixtures & async test client
├── fixtures/
│   ├── polar_samples.json      # Mock Polar run with GPS & HR streams
│   └── concept2_samples.json   # Mock Concept2 row & bike erg sessions
├── unit/
│   ├── test_zone_calculator.py # Unit tests for Zone 1-5 boundary calculations
│   ├── test_security.py        # Token encryption/decryption validation
│   ├── test_polar_adapter.py   # Unit tests for Polar data normalization
│   └── test_concept2_adapter.py# Unit tests for Concept2 data normalization
└── integration/
    ├── test_ingestion_idempotency.py # Tests ensuring 0 duplicates on re-sync
    ├── test_soft_sync.py             # Tests for upstream edit/deletion handling
    └── test_api_endpoints.py         # Full HTTP API integration tests

alembic/
├── versions/                   # Migration scripts
└── env.py                      # Async migration runner

docker-compose.yml              # Standalone PostgreSQL 16 + Coach3 backend containers
Dockerfile                      # Multi-stage Python 3.12 Docker build
pyproject.toml                  # Project dependencies & tool configurations
alembic.ini                     # Migration configuration
```

**Structure Decision**: A modular single-project architecture (`src/` + `tests/`) optimized for FastAPI and async SQLAlchemy with explicit separation between external network adapters (`adapters/`), core business logic (`services/`), domain models (`models/`), and presentation routes (`api/`).

## Complexity Tracking

> **No violations**. All designs strictly adhere to the project constitution, using standard relational PostgreSQL tables and Docker Compose orchestration without extraneous third-party infrastructure.
