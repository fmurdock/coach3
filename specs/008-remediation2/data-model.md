# Data Model: 008-remediation2

**Feature**: [spec.md](spec.md) | **Date**: 2026-11-26

No database schema migrations are required for `008-remediation2`. Existing tables (`workout_sessions`, `strength_sets`, `voice_transcription_logs`, `llm_provider_configs`, `users`) already support all required behaviors.

## Entity Lifecycle Updates

### 1. Active Gym Session (`WorkoutSession` with `provider="coach3_gym"`, `discipline="strength"`)
- **Creation**: Deferred from `GET /api/v1/gym/sessions/active` to `POST /api/v1/gym/sets` (or `POST /api/v1/gym/sessions/{session_id}/sets`).
- **Title**: Formatted in the athlete's configured IANA timezone (`ZoneInfo(user.timezone or "UTC")`): `Gym Strength Session {local_now.strftime('%b %d')}`.
- **Deletion**: Automatically deleted in `DELETE /api/v1/gym/sets/{set_id}` if `session.provider == "coach3_gym"` and `COUNT(strength_sets) == 0` after the set is removed.

### 2. `CommitSetsRequest` (`src/schemas/gym.py`)
- Adds optional `session_id: uuid.UUID | None = None` so `POST /api/v1/gym/sets` can target an explicit session when present or resolve/create one lazily when `None`.

### 3. `ProviderHealthResponse` (`src/schemas/coaching.py`)
- Existing fields (`status`, `latency_ms`, `message`) remain unchanged; `test_connection()` now populates `message` with confirmation of a non-empty model response (or actionable error/Docker-loopback hint).
