# Data Model Specification: Integration Configuration & Workflow Stabilization

**Feature**: `005-integration-config-workflow`  
**Date**: 2026-11-18  
**Status**: Ready  

---

## 1. New Entity: `integration_client_configs`

Persists user-entered OAuth app client credentials securely in the PostgreSQL database, encrypted using Fernet AES-128-CBC with `ENCRYPTION_KEY`.

### Schema Definition
```sql
CREATE TABLE integration_client_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL UNIQUE,
    encrypted_client_id TEXT NOT NULL,
    encrypted_client_secret TEXT NOT NULL,
    redirect_uri VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_client_provider_valid CHECK (provider IN ('polar', 'concept2'))
);
```

### Field Details
- `id` (UUID): Primary key.
- `provider` (VARCHAR(50)): Equipment/telemetry provider identifier (`'polar'` or `'concept2'`). Unique constraint ensures 1 configuration per provider.
- `encrypted_client_id` (TEXT): Encrypted developer client ID.
- `encrypted_client_secret` (TEXT): Encrypted developer client secret.
- `redirect_uri` (VARCHAR(255)): Optional custom callback URI override; if NULL, falls back to server-computed default.
- `is_active` (BOOLEAN): Toggle enabling or disabling the integration connector.
- `created_at` / `updated_at` (TIMESTAMPTZ): Audit timestamps.

---

## 2. Updated Entity: `workout_sessions`

Add an isolation flag to distinguish synthetic demo sessions from authentic athlete telemetry.

### Schema Modification
```sql
ALTER TABLE workout_sessions 
ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_workout_sessions_is_demo ON workout_sessions(is_demo);
```

### Field Details
- `is_demo` (BOOLEAN, default `FALSE`): When `TRUE`, indicates the session was generated via the sample workout seeding utility. Purged cleanly during "Reset Demo Data" without affecting real workouts.

---

## 3. Relationships & Fallback Flow

```mermaid
erDiagram
    INTEGRATION_CLIENT_CONFIGS {
        UUID id PK
        VARCHAR provider UK
        TEXT encrypted_client_id
        TEXT encrypted_client_secret
        VARCHAR redirect_uri
        BOOLEAN is_active
    }

    INTEGRATION_ACCOUNTS {
        UUID id PK
        UUID user_id FK
        VARCHAR provider
        VARCHAR account_id
        TEXT encrypted_access_token
        TEXT encrypted_refresh_token
        TIMESTAMPTZ token_expires_at
        BOOLEAN is_active
    }

    USERS ||--o{ INTEGRATION_ACCOUNTS : "owns"
    INTEGRATION_CLIENT_CONFIGS ..> INTEGRATION_ACCOUNTS : "powers OAuth for"
```

### Credential Resolution Precedence
1. **Database Lookup**: Query `integration_client_configs` where `provider = :provider AND is_active = true`.
2. **Environment Fallback**: If not found in DB or empty, read `settings.POLAR_CLIENT_ID` / `settings.POLAR_CLIENT_SECRET` (or Concept2 equivalent).
3. **Unconfigured**: If neither exists, mark provider status as `unconfigured` with guidance to enter credentials in `/config`.
