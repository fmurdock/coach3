# Quickstart Validation Guide: Core Ingestion & Telemetry

**Feature Branch**: `001-data-ingestion`
**Date**: 2026-11-17
**Status**: Ready for Validation

This guide provides end-to-end steps to run, test, and validate the Core Data Ingestion and Telemetry Models feature.

---

## 1. Prerequisites

- **Docker & Docker Compose** installed.
- **Python 3.12+** (if executing tests or local tooling directly).
- **Environment Configuration**: A valid `.env` file containing local encryption and database settings (see example below).

```bash
# Minimal .env example
DATABASE_URL=postgresql+asyncpg://coach:coach_secret@localhost:5432/coach3_dev
POSTGRES_USER=coach
POSTGRES_PASSWORD=coach_secret
POSTGRES_DB=coach3_dev
ENCRYPTION_KEY=AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA= # 32-byte url-safe base64
POLAR_CLIENT_ID=mock_polar_id
POLAR_CLIENT_SECRET=mock_polar_secret
CONCEPT2_CLIENT_ID=mock_c2_id
CONCEPT2_CLIENT_SECRET=mock_c2_secret
```

---

## 2. Setup & Service Startup

1. **Start Database & Backend**:
   ```bash
   docker compose up -d db
   ```
2. **Apply Database Migrations**:
   ```bash
   alembic upgrade head
   ```
3. **Start Application Server**:
   ```bash
   uvicorn src.main:app --reload --port 8000
   ```
   *(Or start all services via `docker compose up --build`)*

---

## 3. End-to-End Validation Scenarios

### Scenario 1: Configure Heart Rate Zones & Ingest Polar Run (P1)
**Goal**: Verify that a sample outdoor run imported from Polar calculates Zone 2 cardio duration locally using the user's HR profile and stores full GPS coordinate points.

1. **Set User HR Profile**:
   ```bash
   curl -X PUT http://localhost:8000/api/v1/profile/heart-rate \
     -H "Content-Type: application/json" \
     -d '{"resting_hr": 48, "max_hr": 190, "zone1_min": 95, "zone1_max": 114, "zone2_min": 114, "zone2_max": 133, "zone3_min": 133, "zone3_max": 152, "zone4_min": 152, "zone4_max": 171, "zone5_min": 171, "zone5_max": 190}'
   ```
2. **Trigger Mock Ingestion**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/integrations/polar/sync
   ```
3. **Validate Results**:
   ```bash
   curl http://localhost:8000/api/v1/workouts?discipline=outdoor_run
   ```
   *Expected Outcome*: A workout session is returned with `total_distance_m`, `avg_pace_sec_per_km`, and `zone2_duration_sec` populated.
4. **Validate GPS & HR Telemetry**:
   ```bash
   curl http://localhost:8000/api/v1/workouts/{workout_id}/telemetry
   ```
   *Expected Outcome*: JSON payload containing granular `gps_route_points` and `heart_rate_samples`.

---

### Scenario 2: Ingest Concept2 Rower & Erg Bike (P2)
**Goal**: Verify indoor rower and erg bike sessions normalize split times, wattage, and stroke rates into the canonical workout store.

1. **Trigger Concept2 Sync**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/integrations/concept2/sync
   ```
2. **Query Workouts**:
   ```bash
   curl http://localhost:8000/api/v1/workouts?discipline=indoor_row
   curl http://localhost:8000/api/v1/workouts?discipline=erg_bike
   ```
   *Expected Outcome*: Row session displays `avg_split_sec_per_500m`, `avg_power_watts`, and `avg_cadence_spm`.

---

### Scenario 3: Verify Idempotency & Soft-Sync
**Goal**: Re-run the sync and confirm zero duplicate workouts or inflated volume.

1. **Trigger Sync Repeatedly**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/integrations/polar/sync
   curl -X POST http://localhost:8000/api/v1/integrations/polar/sync
   ```
2. **Verify Count**:
   ```bash
   curl http://localhost:8000/api/v1/workouts
   ```
   *Expected Outcome*: The total workout count remains strictly unchanged.
3. **Check Audit Log**:
   ```bash
   curl http://localhost:8000/api/v1/integrations/sync-logs
   ```
   *Expected Outcome*: Latest log records `items_imported: 0, items_updated: N` with status `success`.

---

## 4. Automated Test Suite

Run the full test suite (contract tests, unit tests, and integration tests with mocked API fixtures):

```bash
pytest tests/ -v
```

Reference schemas: [data-model.md](data-model.md)  
Reference API endpoints: [api-ingestion.yaml](contracts/api-ingestion.yaml)
