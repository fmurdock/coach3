# Data Model & Schema Remediation: Coach3 (`007-remediation`)

**Date**: 2026-11-24  
**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## Overview of Schema Evolution

All database changes will be delivered in a single, lossless, fully reversible Alembic migration (`006_remediation_hardening.py`, revising `005_integration_config_and_demo`), plus cleanup of ORM model definitions (`src/models/`) to eliminate SQLite-vs-PostgreSQL dialect drift and eager-loading memory bombs.

---

## 1. Entity Updates & New Entities

### 1.1 `users` (Modified)
Represents the single self-hosted athlete profile and operational preferences.

| Column | Type | Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | PK | Existing athlete identifier |
| `timezone` | `String(64)` | `NOT NULL`, `server_default='UTC'` | **NEW**: Athlete IANA timezone (e.g., `America/Los_Angeles`) for local day/week analytics bucketing (`FR-038`) |
| `passphrase_hash` | `Text` | `NULL` | **NEW**: Optional scrypt passphrase hash (`scrypt$salt$hash`) if configured/updated in DB (`FR-005`) |
| `created_at` | `DateTime(tz=True)` | `NOT NULL` | Existing |
| `updated_at` | `DateTime(tz=True)` | `NOT NULL` | Existing |

**Validation Rules**:
- `timezone` MUST be a valid IANA timezone recognized by `zoneinfo.ZoneInfo`.

---

### 1.2 `oauth_states` (New)
Stores single-use, expiring OAuth2 CSRF `state` nonces (`FR-006`).

| Column | Type | Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `state` | `String(128)` | PK | Cryptographically random URL-safe nonce (`secrets.token_urlsafe(32)`) |
| `user_id` | `UUID` | FK `users.id` (`ON DELETE CASCADE`), `NOT NULL` | Owning athlete |
| `provider` | `String(50)` | `NOT NULL`, `CHECK (provider IN ('polar', 'concept2'))` | Target OAuth provider |
| `expires_at` | `DateTime(tz=True)` | `NOT NULL`, indexed | Expiration timestamp (default +10 minutes) |
| `created_at` | `DateTime(tz=True)` | `NOT NULL` | Creation timestamp |

**State Transitions**:
- `Created` (`GET /integrations/{provider}/auth-url`) → `Consumed & Deleted` (`GET /integrations/{provider}/callback` on exact match where `expires_at > now` and `provider` matches) OR `Expired & Pruned`.

---

### 1.3 `user_heart_rate_profiles` (Modified Constraint)
Tightens physiological validation while allowing elite low resting HR (`FR-030`).

- **Updated Check Constraint (`check_hr_bounds`)**:
  - `resting_hr >= 25 AND resting_hr < 150 AND max_hr > 120 AND max_hr < 240 AND resting_hr < max_hr`
- **Added Check Constraint (`check_hr_zones_ordered`)**:
  - `zone1_min > 0 AND zone1_min < zone1_max AND zone1_max <= zone2_min AND zone2_min < zone2_max AND zone2_max <= zone3_min AND zone3_min < zone3_max AND zone3_max <= zone4_min AND zone4_min < zone4_max AND zone4_max <= zone5_min AND zone5_min < zone5_max`

---

### 1.4 `strength_sets` (Modified)
Fixes prefix-collision and multi-candidate idempotency bugs (`FR-021`).

| Column | Type | Constraints | Purpose |
| :--- | :--- | :--- | :--- |
| `submission_key` | `String(100)` | `NULL`, indexed (`idx_strength_set_submission`) | **NEW**: Exact client-generated submission idempotency key (`CommitSetsRequest.idempotency_key`) for collision-free exact retry lookup |
| `idempotency_key` | `String(120)` | `UNIQUE`, `NULL` | Existing per-row unique key, now consistently formatted as `f"{submission_key}:{row_seq}"` for every row in a submission |

- **Removed redundant index**: Drop duplicate `idx_strength_set_idempotency` if redundant with column unique constraint (keep one canonical unique index).
- **Backfill on upgrade**: Existing rows keep their existing `idempotency_key`; `submission_key` defaults to `NULL` for historical rows.

---

### 1.5 `llm_provider_configs` & `coaching_philosophies` (Modified)
Hardens secret storage length and enforces single-active invariant at DB level (`FR-035`).

- **`llm_provider_configs`**:
  - Alter `api_key_encrypted` from `String(500)` → `Text` (Fernet ciphertexts expand with plaintext length).
  - Add PostgreSQL partial unique index:
    `CREATE UNIQUE INDEX uq_llm_provider_active_user ON llm_provider_configs (user_id) WHERE is_active = true;`
- **`coaching_philosophies`**:
  - Add PostgreSQL partial unique index:
    `CREATE UNIQUE INDEX uq_coaching_philosophy_active_user ON coaching_philosophies (user_id) WHERE is_active = true;`
  - Add check constraints: `target_zone2_pct >= 0 AND target_zone2_pct <= 100`, `max_rpe_threshold >= 1 AND max_rpe_threshold <= 10`, `min_rest_days_per_week >= 0 AND min_rest_days_per_week <= 7`, `primary_modality IN ('endurance', 'strength', 'hybrid')`.

---

### 1.6 `integration_client_configs` & `strength_exercises` / `exercise_aliases` (Index & Relationship Hygiene)
- Drop redundant non-unique index `ix_client_configs_provider` on `integration_client_configs(provider)` (already covered by `uq_client_config_provider`).
- Align ORM definitions so `strength_exercises.slug` and `exercise_aliases.alias` do not declare duplicate `unique=True` + explicit unique `Index`.
- Standardize `JSON_TYPE = JSON().with_variant(JSONB, "postgresql")` across `integration.py`, `workout.py`, `voice_log.py`, and `coaching.py` (replacing raw `postgresql.JSONB` in ORM models so SQLite & PostgreSQL remain consistent).
- **ORM Loading Policy (`FR-025`, `FR-027`)**:
  - `StrengthExercise.sets`: change `lazy="selectin"` → `lazy="select"` (never auto-load historical sets).
  - `WorkoutSession.strength_sets` & `WorkoutSession.voice_logs`: change `lazy="selectin"` → `lazy="select"` (use explicit `selectinload` only in detail queries).
  - `WorkoutSession.heart_rate_samples` & `gps_route_points`: remain default lazy, loaded only in detail/telemetry/export/batched-recalc queries.

---

### 1.7 `personal_records` (Removed Dead Table)
- **Decision (`R8`, `FR-035`)**: Drop unused `personal_records` table in migration `006` (with full table/index recreation in `downgrade()`) and remove `src/models/personal_record.py`.
- **Rationale**: `PRDetectorService` computes PRs dynamically and deterministically from `strength_sets` and `workout_sessions`. Removing the unused table prevents schema clutter and avoids cache-invalidation drift when strength sets are deleted or workouts are edited.

---

### 1.8 `sync_audit_logs` (Operational Lifecycle & Retention)
No breaking column changes; enforce lifecycle state machine (`FR-012`, `FR-039`, `FR-044`):

```text
running ──(all pages persisted & remote committed)──► success
   │
   ├──(HTTP/DB/validation error, transaction rolled back)──► failed (with sanitized error_message)
   │
   └──(orphaned on process restart / startup sweep)──► failed ("Interrupted by server restart")
```

- **Retention**: Prune `sync_audit_logs` older than 90 days (keeping at least the latest 50 rows per provider) during scheduled cleanup so operational logs remain bounded over multi-year deployments.

---

## 2. Deterministic Exercise Identifiers (`FR-020`)

All canonical exercises use one deterministic UUID formula everywhere (`ExerciseCatalogService`, `seed_exercises.py`, `SeedService.ensure_default_exercises`):

```text
exercise_id = uuid5(NAMESPACE_DNS, f"coach3.exercise.{slug}")
```

- When upgrading an existing DB where `SeedService` or `seed_exercises.py` previously inserted a `uuid4()` row for a canonical `slug`, `ExerciseCatalogService.load_from_db()` loads the **actual DB row's `id`** into memory at startup AND `gym.py` resolves incoming candidates by `(id OR slug)` before ever attempting an `INSERT`. Thus both upgraded DBs and fresh DBs work seamlessly with zero `UniqueViolation` or FK errors.

---

## 3. Client-Side Offline Queue Model (`FR-024`)

Stored in browser `localStorage` under key `coach3_gym_offline_queue_v1`:

```json
[
  {
    "queue_id": "uuid-v4",
    "session_id": "uuid-or-null",
    "created_at": "2026-11-24T20:00:00.000Z",
    "payload": {
      "idempotency_key": "uuid-v4",
      "raw_transcript": "...",
      "confidence_score": 0.95,
      "was_edited": false,
      "original_parsed_sets": [...],
      "sets": [...]
    }
  }
]
```

- On reconnect (`online` event or `/gym` load), queued items are flushed FIFO using their preserved `idempotency_key` (resolving `/api/v1/gym/sessions/active` if `session_id` is stale/missing). Successful entries are removed atomically; transient network errors remain queued without duplicates.
