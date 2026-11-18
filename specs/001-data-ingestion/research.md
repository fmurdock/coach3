# Research & Architectural Decisions: Core Data Ingestion & Telemetry Models

**Feature Branch**: `001-data-ingestion`
**Date**: 2026-11-17
**Status**: Completed

## 1. Technical Decisions

### Decision 1: Framework & Core Stack (Python + FastAPI + SQLAlchemy 2.0 Async)
- **Decision**: Python 3.12 with FastAPI, Pydantic v2, and SQLAlchemy 2.0 (asyncio with `asyncpg`) managed by Alembic.
- **Rationale**: 
  - FastAPI provides native async support, high performance, automatic OpenAPI documentation, and strict request/response validation via Pydantic v2.
  - SQLAlchemy 2.0 async with `asyncpg` provides asynchronous database I/O to handle concurrent telemetry ingestion and database queries without thread blocking.
  - Alembic guarantees clean, version-controlled database schema migrations.
- **Alternatives Considered**:
  - *Django / Django ORM*: Overkill for a headless API backend; heavier memory footprint on self-hosted servers.
  - *SQLModel*: While convenient, direct SQLAlchemy 2.0 + Pydantic v2 affords greater control over complex relationships, composite unique indexes, and partition-ready telemetry tables.

### Decision 2: Database Schema & Storage (PostgreSQL 16 in Docker Compose)
- **Decision**: PostgreSQL 16 containerized via Docker Compose. Normalized relational schema with composite unique indexes on `(provider, external_workout_id)` for idempotency, plus time-series tables for `heart_rate_samples`, `workout_splits`, and `gps_route_points`.
- **Rationale**:
  - PostgreSQL handles relational domain models, transaction safety, and time-series telemetry streams natively with B-tree and composite indexing.
  - Standard PostgreSQL avoids non-standard binary extensions (like PostGIS), making self-hosting straightforward, portable, and reliable across hardware architectures (x86_64 and ARM64 / Apple Silicon).
  - Standalone Docker Compose provisions both the database and the backend service automatically.
- **Alternatives Considered**:
  - *PostgreSQL + PostGIS*: PostGIS adds geographic query functions, but for simply storing, displaying, and exporting run routes, standard latitude/longitude/elevation/timestamp points with spatial bounding boxes and GeoJSON export are simpler and have zero dependency friction.
  - *SQLite*: Lacks concurrent write throughput needed when long-running historical backfill jobs run in parallel with real-time queries.

### Decision 3: Credential Encryption & Data Sovereignty
- **Decision**: Store external OAuth tokens (Polar AccessLink tokens, Concept2 Logbook API tokens) and client secrets in the database encrypted at rest using AES-128-CBC / HMAC-SHA256 authenticated symmetric encryption via `cryptography.fernet`.
- **Rationale**:
  - Adheres strictly to Constitution Principle I (Data Sovereignty) by ensuring third-party credentials cannot be read in plaintext even if a raw database dump is accessed.
  - Encryption key is injected via an environment variable (`ENCRYPTION_KEY`) generated during initial setup.
- **Alternatives Considered**:
  - *Plaintext storage*: Unacceptable security risk.
  - *External secrets managers (HashiCorp Vault, AWS Secrets Manager)*: Too complex for self-hosted home servers.

### Decision 4: Background Scheduling & Execution
- **Decision**: Use `APScheduler` (`AsyncIOScheduler`) running within the FastAPI application lifecycle for fixed 60-minute recurring background synchronization, paired with an asynchronous task queue or in-process queue for on-demand manual triggers and historical backfill jobs.
- **Rationale**:
  - Lightweight, runs in the same container process without requiring Redis or Celery support infrastructure.
  - Perfectly matches the fixed hourly schedule decided in the clarification session, while allowing immediate `Sync Now` triggers via API endpoints.
- **Alternatives Considered**:
  - *Celery + Redis*: Requires two additional server containers (Redis broker + Celery worker), unnecessary operational overhead for a single-user self-hosted coach.
  - *System cron*: Harder to orchestrate inside Docker Compose and lacks integration with application state.

### Decision 5: External API Ingestion & Rate-Limit Resilience
- **Decision**: Encapsulate Polar AccessLink and Concept2 Logbook API interactions in modular client adapters using `httpx.AsyncClient` with exponential backoff and jitter for HTTP 429 and transient 5xx errors.
- **Rationale**:
  - Isolates external API specifics (OAuth2 refresh flows, payload nuances, pagination cursors) behind clean domain interfaces (`PolarAdapter`, `Concept2Adapter`).
  - Supports checkpointed progress during full historical backfills so interrupted imports resume without re-fetching old pages.
- **Alternatives Considered**:
  - *Synchronous `requests`*: Blocks event loop during multi-minute historical syncs.

---

## 2. Risk Assessment & Mitigations

| Risk | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Polar AccessLink OAuth Expiration** | Medium | Adapter automatically checks token expiration timestamps and calls the refresh endpoint before requesting transaction endpoints. |
| **API Rate Limits during Full Historical Backfill** | High | Adapters implement rate-limiting throttles and parse `Retry-After` headers; backfill records cursor checkpoints in `IntegrationAccount.sync_cursor`. |
| **Large GPS / HR Telemetry Storage** | Low | Batch insertion (`executemany`) for telemetry samples; indexed by `workout_id` and timestamp; optional compression. |
