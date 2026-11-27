# Quickstart Validation Guide: 008-remediation2

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## 1. Automated Verification
```bash
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest -W default -v
```
Expected: zero lint/type errors and all unit/integration tests passing, including:
- Lazy gym session creation & empty-session cleanup on last-set deletion (`tests/integration/test_gym_api.py`).
- LLM prompt-and-output connection verification (`tests/unit/test_llm_client.py` and `tests/integration/test_coaching_api.py`).

## 2. Manual End-to-End Verification
1. Rebuild & restart the app container:
   ```bash
   docker compose up --build -d app
   ```
2. **No Blank Workouts**:
   - Visit `http://localhost:8000/gym` and navigate away without logging any sets.
   - Open `/dashboard` and confirm no `0`-set `Gym Strength Session` was created.
   - Return to `/gym`, log `"bench press 225 lbs 3x5"`, confirm it creates the session with today's local date, then delete all logged sets and confirm the empty session is removed from `/dashboard`.
3. **Cardio & Lifting Dashboard Tabs**:
   - Open `/dashboard`, switch between **Cardio** and **Lifting** tabs across `7d` / `30d` / `all`, and verify each tab shows only its modality's metrics, charts, PRs, and workout rows.
4. **Professional UI Polish**:
   - Inspect `/dashboard`, `/gym`, `/coach`, `/config`, and `/login` on desktop and mobile widths to confirm calm, restrained surfaces, clear contrast, and no flashy gradients/glows.
5. **LLM Server Connection**:
   - In `/config` or `/coach`, configure a Gemini or local `llama.cpp` provider and click **Test Connection**; verify a healthy status when reachable and a clear actionable message when unreachable.
