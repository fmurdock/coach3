# Coach3

Self-hosted workout tracker, volume analytics, and adaptive AI fitness coach.

Coach3 runs entirely on user-controlled hardware (local desktop, home server, or homelab container), keeping cardiovascular telemetry, biometrics, audio transcripts, and coaching philosophies private.

---

## Architecture & Core Features

Coach3 brings together 4 integrated modules accessible through a unified, CSP-hardened web shell:

```mermaid
flowchart LR
    subgraph Inputs [Multimodal Inputs]
        Voice["🎙️ Gym Mode<br>(/gym)"]
        Polar["🏃 Polar AccessLink<br>(Runs & HR)"]
        C2["🚣 Concept2 Logbook<br>(Rower & Bike)"]
    end

    subgraph Core [FastAPI Core Services]
        Norm["Volume & PR Engine<br>(Zone 2, Epley 1RM)"]
        AI["Adaptive Coach<br>(Gemini / llama.cpp)"]
    end

    subgraph UI [Unified Web Interface]
        GymUI["/gym<br>Voice Logging"]
        DashUI["/dashboard<br>Volume & PRs"]
        CoachUI["/coach<br>Critique & Plans"]
        ConfigUI["/config<br>Integrations & Settings"]
    end

    Voice --> Norm
    Polar --> Norm
    C2 --> Norm
    Norm --> DashUI
    Norm --> AI
    AI --> CoachUI
    ConfigUI -.-> Polar
    ConfigUI -.-> C2
    ConfigUI -.-> AI
```

1. **🎙️ Gym Voice Logging (`/gym`)**: Mobile-optimized voice logging for strength workouts with multi-clause parsing, exercise editing, session reload restoration, `localStorage` offline queueing with automatic online flush, and one-tap set deletion.
2. **📊 Training Volume & Performance Dashboard (`/dashboard`)**: Weekly goal-tracked macro charts for **Zone 2 Cardio** (`120 min/wk` goal) and **VO2 Max Training** (`20 min/wk` Zone 5 goal) bucketed in your configured IANA timezone, plus **Push / Pull / Legs / Abs** resistance volume (`10 sets/wk` goal each, paired top lift & canonical Epley 1RM). Includes paginated workout history, inline title/notes editing, Mercator SVG GPS route maps, and honest measured pace telemetry.
3. **🤖 Adaptive AI Coaching (`/coach`)**: Retrospective workout critiques (Analysis Mode) and validated 7-day or 14-day microcycles (Planning Mode) with completion checkboxes, per-user concurrency locks, and strict PII scrubbing before cloud dispatch.
4. **⚙️ Integrations, Export & Diagnostics Hub (`/config`)**: In-browser configuration for Polar AccessLink, Concept2 Logbook, AI inference engines, Heart Rate Zones (supporting elite resting HR ≥ 25 bpm), Athlete Timezone, one-click lossless ZIP backup export, and a **System Health & Sync Diagnostics** card.

---

## Quickstart & Local Setup

### 1. Prerequisites
- Python 3.12+
- PostgreSQL 16 (or Docker Compose)

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Generate a required Fernet encryption key (the server refuses to boot in non-test environments without a valid, non-placeholder `ENCRYPTION_KEY`):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Key security & runtime variables in `.env`:
| Variable | Purpose |
| :--- | :--- |
| `ENCRYPTION_KEY` | **Required.** Fernet key encrypting OAuth credentials and LLM API keys at rest. |
| `COACH3_PASSPHRASE` | Single-user sign-in passphrase (hashed with `scrypt`, backed by `HttpOnly` `SameSite=Lax` HMAC session cookie). |
| `AUTH_DISABLED_LOCALHOST` | Opt-in loopback bypass (`true` allowed only when `ENVIRONMENT=development` or `test`). |
| `ALLOWED_ORIGINS` | Comma-separated explicit CORS allowlist (never `*` with credentials). |
| `TRUST_PROXY_HEADERS` / `TRUSTED_PROXY_IPS` | Trust `X-Forwarded-Proto` / `X-Forwarded-For` only from listed reverse-proxy IPs. |
| `ALLOW_PRIVATE_LLM_HOSTS` | Explicit comma-separated LAN allowlist for self-hosted `llama.cpp` endpoints (SSRF guard). |
| `PRIVACY_SCRUB_TERMS` | Optional custom terms (e.g., athlete name or city) scrubbed from outbound LLM prompts. |

### 3. Docker Compose (Automatic Migrations)
```bash
docker compose up --build -d
```
The container runs as non-root user `coach3`, automatically executes `alembic upgrade head` on startup via `docker-entrypoint.sh`, binds PostgreSQL strictly to `127.0.0.1:5432`, and exposes a database-aware `/health` check.

### 4. Local Development Server
```bash
docker compose up -d db
.venv/bin/alembic upgrade head
.venv/bin/uvicorn src.main:app --reload --port 8000
```

---

## Web Interfaces & Data Export

| Interface | URL | Purpose |
| :--- | :--- | :--- |
| **Sign In** | `http://localhost:8000/login` | Passphrase login (when auth is active). |
| **Settings & Diagnostics** | `http://localhost:8000/config` | Polar/Concept2 credentials, AI provider, HR zones, Timezone, ZIP Export, and System Diagnostics. |
| **Gym Voice Logger** | `http://localhost:8000/gym` | Mobile voice/text logging with multi-clause review & offline queue. |
| **Volume Dashboard** | `http://localhost:8000/dashboard` | Weekly macro volume, PRs, paginated workout history, and inline notes editor. |
| **AI Fitness Coach** | `http://localhost:8000/coach` | Philosophy steering, critiques, and interactive training schedule. |
| **Training History Export** | `GET /api/v1/export` | Downloads `coach3-backup-YYYYMMDD.zip` containing lossless `backup.json`, `workouts.csv`, and `strength_sets.csv` (excludes encrypted secrets and demo records by default). |
| **System Diagnostics** | `GET /api/v1/system/diagnostics` | Database reachability, Alembic schema revision, scheduler next-run timestamp, provider decryption health, and latest 10 sync audit logs. |

---

## Demo Data & Testing Tools

- **From UI**: Visit `/config` and click **Load Sample Workouts** or **Reset Demo Data**.
- **From Terminal**:
  ```bash
  python -m src.scripts.seed_demo
  python -m src.scripts.seed_demo --reset
  ```
  *(Purges only synthetic `is_demo=True` workouts; authentic athlete data and credentials are never deleted.)*

---

## Verification, Linting & Type Checking

```bash
# Full automated test suite (zero deprecation warnings)
.venv/bin/pytest -W default -v

# Lint & security checks (E, F, W, S, B)
.venv/bin/ruff check src tests

# Static type checking
.venv/bin/mypy src

# Real PostgreSQL Alembic round-trip & constraint verification
TEST_DATABASE_URL=postgresql+asyncpg://coach3:coach3@127.0.0.1:5432/coach3_test \
  .venv/bin/pytest tests/integration/test_postgres_migrations.py -v
```

---

## Constitution & Data Sovereignty

Coach3 operates under `.specify/memory/constitution.md`:
* **Data Sovereignty**: 100% of telemetry, workout logs, and credentials reside on self-hosted storage with one-click lossless ZIP export.
* **Privacy Scrubbing**: Outbound LLM prompts are stripped of emails, phone numbers, IPv4/IPv6 addresses, GPS coordinate pairs, raw route tracks, and configured custom PII terms.
* **Lossless Sync & Idempotency**: Polar AccessLink transactions are committed remotely only after durable database persistence; Concept2 syncs paginate completely before advancing watermarks; voice set submissions enforce exact `submission_key` idempotency.
