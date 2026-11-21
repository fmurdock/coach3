# Implementation Plan: Integration Configuration & Workflow Stabilization

**Branch**: `feature/005-integration-config-workflow` | **Date**: 2026-11-18 | **Spec**: [specs/005-integration-config-workflow/spec.md](spec.md)

**Input**: Feature specification from `specs/005-integration-config-workflow/spec.md`

---

## Summary

Deliver a self-hosted configuration hub, seamless integration onboarding, and holistic system stabilization for Coach3:
1. **Dynamic Credential Persistence**: Store encrypted Polar and Concept2 developer client credentials in the PostgreSQL database (`integration_client_configs`) with transparent `.env` fallback and zero-restart configuration.
2. **Robust OAuth & Diagnostic Verification**: Add `GET /api/v1/integrations/{provider}/callback` for automated browser redirects and `POST /api/v1/integrations/{provider}/verify` for token health checks and athlete identity diagnostics.
3. **Unified Settings Hub**: Centralize telemetry integrations (Polar, Concept2) and AI Inference Providers (Gemini, local `llama.cpp`) in a single `/config` interface.
4. **Universal Responsive Navigation Shell**: Embed a unified navigation bar across `/gym`, `/dashboard`, `/coach`, and `/config` with active route highlighting.
5. **Isolated Demo Seeding & Reset**: Provide a one-click UI action and terminal CLI script (`python -m src.scripts.seed_demo`) to populate realistic running, rowing, and strength telemetry with safe, isolated demo purging.

---

## Technical Context

**Language/Version**: Python 3.12 (backend), Modern HTML5/ES6 (frontend).

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic, `httpx` (async HTTP for Polar AccessLink, Concept2 Logbook, and LLM providers), `cryptography` (Fernet symmetric encryption).

**Storage**: PostgreSQL 16 (new table: `integration_client_configs`, updated table: `workout_sessions` with `is_demo` boolean).

**Testing**: `pytest`, `pytest-asyncio`, `httpx` (mock transports for OAuth token exchange, credential encryption roundtrips, and diagnostic pings).

**Target Platform**: Self-hosted Docker container / local machine (port 8000/8001); mobile Safari (iPhone) and desktop browsers.

**Project Type**: Monorepo web service (FastAPI API + server-rendered static frontend apps).

**Performance Goals**:
- Diagnostic verification response latency $< 1500\text{ms}$.
- Configuration UI render latency $< 100\text{ms}$ with zero external CDN dependencies.
- Demo data seeding $< 2\text{s}$ for a full 2-week multi-modal workout bundle.

**Constraints**:
- Strictly self-hosted data sovereignty (Constitution Principle I).
- 100% encrypted token and credential storage at rest.
- Demo data purging must be isolated (`is_demo == true`) and never touch authentic workout sessions.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Design Status | Compliance Assessment |
|---|---|---|---|
| **I. Self-Hosted Architecture & Sovereignty** | Self-hosted storage; zero third-party telemetry leakage; local credentials. | **PASS** | Developer credentials and OAuth tokens are stored exclusively in local PostgreSQL, encrypted with `ENCRYPTION_KEY`. No telemetry leaves self-hosted perimeter. |
| **II. Modular Ingestion & Source Isolation** | Independent adapters for Polar and Concept2; idempotent sync. | **PASS** | Preserves decoupling of `PolarAdapter` and `Concept2Adapter`; verification tests connection health without mutating canonical workout data. |
| **III. Multimodal Ergonomics & Robustness** | Mobile-optimized interface; fault tolerance. | **PASS** | Adds unified mobile-responsive navigation across `/gym`, `/dashboard`, `/coach`, and `/config` with copyable callback URLs and error toast notifications. |
| **IV. Unified Volume Modeling & Peak Analytics** | Canonical metrics normalized across modalities. | **PASS** | Demo seed populates canonical running, rowing, and strength workouts with valid HR zones, wattages, and set loads that feed directly into analytics engines. |
| **V. Philosophy-Steered AI Coaching** | Decoupled philosophy and provider settings. | **PASS** | Centralizes provider configuration in `/config` while maintaining active philosophy steering and model execution on `/coach`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/005-integration-config-workflow/
├── spec.md              # Feature specification with clarifications
├── plan.md              # Architecture and implementation plan (this file)
├── research.md          # Technical research & decisions
├── data-model.md        # Database schema modifications
├── quickstart.md        # Step-by-step verification scenarios
├── contracts/           # OpenAPI 3.1 specification
│   └── api-config.yaml
└── checklists/
    └── requirements.md  # Specification quality validation checklist
```

### Source Code Layout

```text
src/
├── api/
│   ├── config.py               # Endpoints: /api/v1/config/integrations
│   ├── integrations.py         # Added /callback and /verify routes
│   ├── admin.py                # Endpoints: /api/v1/admin/demo/seed and DELETE /demo
│   └── router.py               # Mounts config and admin routers
├── core/
│   ├── config.py               # Settings with DB credential lookup fallback
│   └── security.py             # Reused encrypt_token / decrypt_token
├── models/
│   ├── integration.py          # Added IntegrationClientConfig model
│   ├── workout.py              # Added is_demo boolean column
│   └── __init__.py             # Exports updated models
├── schemas/
│   └── config.py               # Pydantic schemas for configs, verification, and seeding
├── scripts/
│   └── seed_demo.py            # CLI runnable demo seeding script
├── services/
│   ├── config_service.py       # Credential resolution & verification logic
│   └── seed_service.py         # Demo data generation & safe purge engine
├── static/
│   ├── config.html             # Dedicated configuration & setup guide UI
│   ├── coach.html              # Updated with unified navigation header
│   ├── dashboard.html          # Updated with unified navigation header
│   └── gym.html                # Updated with unified navigation header
└── main.py                     # Mounts /config route
```

---

## Planned Execution Phases

### Phase 1: Database Schema & Core Services
1. Create Alembic migration `005_integration_client_configs.py` (table `integration_client_configs`, column `workout_sessions.is_demo`).
2. Add `IntegrationClientConfig` SQLAlchemy model in `src/models/integration.py`.
3. Add `src/schemas/config.py` Pydantic models.
4. Implement `ConfigService` in `src/services/config_service.py` to encrypt/decrypt client credentials and resolve credentials with `.env` fallback.

### Phase 2: Ingestion Adapter Callbacks & Verification
1. Add `GET /api/v1/integrations/{provider}/callback` endpoint in `src/api/integrations.py` to handle browser OAuth redirects and save tokens.
2. Implement verification methods in `PolarAdapter` and `Concept2Adapter` to ping provider profile endpoints and refresh tokens.
3. Expose `POST /api/v1/integrations/{provider}/verify`.

### Phase 3: Demo Data Seed & Reset Engine
1. Implement `SeedService` in `src/services/seed_service.py` creating realistic multi-modal workouts with `is_demo=True`.
2. Implement clean purge in `SeedService.purge_demo_data()`.
3. Create CLI script `src/scripts/seed_demo.py` and API endpoints `POST /api/v1/admin/demo/seed` and `DELETE /api/v1/admin/demo`.

### Phase 4: UI Configuration Hub & Universal Navigation Shell
1. Create `src/static/config.html` containing:
   - Polar AccessLink setup card with copyable callback URL, credential inputs, Connect button, and Verify Connection diagnostic badge.
   - Concept2 Logbook setup card with copyable callback URL, credential inputs, Connect button, and Verify Connection diagnostic badge.
   - AI Inference Provider card (Gemini / llama.cpp) with test ping.
   - Demo Data & Testing card (Load Sample Workouts, Reset Demo Data).
2. Embed the unified, responsive top navigation bar in `src/static/gym.html`, `src/static/dashboard.html`, `src/static/coach.html`, and `src/static/config.html`.
3. Register `/config` route in `src/main.py`.

### Phase 5: Verification & Quality Assurance
1. Unit tests for `ConfigService`, `SeedService`, and OAuth callback handling.
2. End-to-end verification following `quickstart.md`.
