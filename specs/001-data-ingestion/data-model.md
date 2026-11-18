# Data Model: Core Ingestion & Telemetry Schema

**Feature Branch**: `001-data-ingestion`
**Date**: 2026-11-17
**Status**: Completed

## 1. Relational Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o| USER_HEART_RATE_PROFILE : "configures"
    USER ||--o{ INTEGRATION_ACCOUNT : "links"
    USER ||--o{ WORKOUT_SESSION : "owns"
    USER ||--o{ SYNC_AUDIT_LOG : "triggers"

    WORKOUT_SESSION ||--o{ HEART_RATE_SAMPLE : "contains"
    WORKOUT_SESSION ||--o{ GPS_ROUTE_POINT : "contains"
    WORKOUT_SESSION ||--o{ WORKOUT_SPLIT : "contains"

    INTEGRATION_ACCOUNT {
        uuid id PK
        uuid user_id FK
        string provider
        string account_id
        text encrypted_access_token
        text encrypted_refresh_token
        timestamp token_expires_at
        jsonb sync_cursor
        timestamp last_sync_at
        boolean is_active
    }

    USER_HEART_RATE_PROFILE {
        uuid id PK
        uuid user_id FK
        int resting_hr
        int max_hr
        int zone1_min
        int zone1_max
        int zone2_min
        int zone2_max
        int zone3_min
        int zone3_max
        int zone4_min
        int zone4_max
        int zone5_min
        int zone5_max
    }

    WORKOUT_SESSION {
        uuid id PK
        uuid user_id FK
        string provider
        string external_id
        string discipline
        string title
        timestamp start_time_utc
        string local_timezone
        float total_duration_sec
        float active_duration_sec
        float total_distance_m
        int total_calories
        int avg_heart_rate
        int max_heart_rate
        float zone1_duration_sec
        float zone2_duration_sec
        float zone3_duration_sec
        float zone4_duration_sec
        float zone5_duration_sec
        float avg_pace_sec_per_km
        float elevation_gain_m
        float elevation_loss_m
        int total_strokes
        float avg_cadence_spm
        float avg_power_watts
        float avg_split_sec_per_500m
        int avg_drag_factor
        string status
        text user_notes
        jsonb raw_summary
        timestamp created_at
        timestamp updated_at
    }

    HEART_RATE_SAMPLE {
        bigint id PK
        uuid workout_id FK
        timestamp timestamp_utc
        float elapsed_sec
        int bpm
    }

    GPS_ROUTE_POINT {
        bigint id PK
        uuid workout_id FK
        timestamp timestamp_utc
        float elapsed_sec
        double_precision latitude
        double_precision longitude
        float altitude_m
    }

    WORKOUT_SPLIT {
        uuid id PK
        uuid workout_id FK
        int split_index
        string split_type
        float distance_m
        float duration_sec
        float avg_pace_sec_per_km
        float avg_power_watts
        float avg_cadence_spm
        int avg_heart_rate
        float avg_split_sec_per_500m
    }

    SYNC_AUDIT_LOG {
        uuid id PK
        uuid user_id FK
        string provider
        string trigger_type
        timestamp started_at
        timestamp completed_at
        string status
        int items_imported
        int items_updated
        text error_message
        jsonb diagnostic_metadata
    }
```

---

## 2. Table Definitions & Constraints

### `integration_account`
Stores encrypted provider credentials and synchronization watermarks.
- **Constraints**:
  - `PRIMARY KEY (id)`
  - `FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE`
  - `UNIQUE (user_id, provider)`
  - `CHECK (provider IN ('polar', 'concept2'))`

### `user_heart_rate_profile`
Maintains individual heart rate zones for local zone calculation.
- **Constraints**:
  - `PRIMARY KEY (id)`
  - `FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE`
  - `UNIQUE (user_id)`
  - `CHECK (resting_hr > 30 AND max_hr < 240 AND resting_hr < max_hr)`
  - `CHECK (zone1_min < zone1_max AND zone1_max <= zone2_min AND zone2_min < zone2_max AND zone2_max <= zone3_min ...)`

### `workout_session`
Canonical normalized entity for all endurance activities.
- **Constraints**:
  - `PRIMARY KEY (id)`
  - `FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE`
  - `UNIQUE (provider, external_id)` — **Enforces Ingestion Idempotency**
  - `CHECK (discipline IN ('outdoor_run', 'indoor_row', 'erg_bike'))`
  - `CHECK (status IN ('active', 'archived_upstream'))`
- **Indexes**:
  - `CREATE INDEX idx_workout_user_date ON workout_session (user_id, start_time_utc DESC);`
  - `CREATE INDEX idx_workout_discipline ON workout_session (user_id, discipline, start_time_utc DESC);`

### `heart_rate_sample`
Time-series cardiovascular samples.
- **Constraints**:
  - `PRIMARY KEY (id)`
  - `FOREIGN KEY (workout_id) REFERENCES workout_session (id) ON DELETE CASCADE`
- **Indexes**:
  - `CREATE INDEX idx_hr_workout_elapsed ON heart_rate_sample (workout_id, elapsed_sec ASC);`

### `gps_route_point`
High-resolution geographic coordinate stream for outdoor runs.
- **Constraints**:
  - `PRIMARY KEY (id)`
  - `FOREIGN KEY (workout_id) REFERENCES workout_session (id) ON DELETE CASCADE`
- **Indexes**:
  - `CREATE INDEX idx_gps_workout_elapsed ON gps_route_point (workout_id, elapsed_sec ASC);`

### `workout_split`
Sub-session segment metrics (kilometer splits, 500m intervals).
- **Constraints**:
  - `PRIMARY KEY (id)`
  - `FOREIGN KEY (workout_id) REFERENCES workout_session (id) ON DELETE CASCADE`
- **Indexes**:
  - `CREATE INDEX idx_split_workout_order ON workout_split (workout_id, split_index ASC);`

### `sync_audit_log`
Tracks operational health, audit history, and error diagnostics.
- **Constraints**:
  - `PRIMARY KEY (id)`
  - `FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE`
- **Indexes**:
  - `CREATE INDEX idx_sync_log_user ON sync_audit_log (user_id, started_at DESC);`
