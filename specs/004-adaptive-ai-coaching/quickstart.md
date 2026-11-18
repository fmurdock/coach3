# Quickstart & Verification Scenarios: Adaptive AI Coaching Engine

**Feature**: `004-adaptive-ai-coaching`  
**Date**: 2026-11-18  
**Status**: Ready for Verification  

This quickstart guides you through validating the dual-engine LLM connections, philosophy steering with manual context loading, retrospective workout critiques, forward schedule generation, and the visual coaching web interface.

---

## 1. Environment & Setup

Ensure the server is running on port 8001:
```bash
.venv/bin/uvicorn src.main:app --port 8001 --reload
```

---

## 2. Verification Scenarios

### Scenario A: Save & Test Inference Provider Health
Save a local `llama.cpp` server or Google Gemini API configuration and test connectivity:
```bash
# 1. Save provider (llama.cpp)
curl -X POST "http://localhost:8001/api/v1/coaching/providers" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "llama_cpp",
    "endpoint_url": "http://localhost:8080/v1",
    "model_name": "qwen2.5-14b-instruct",
    "temperature": 0.7
  }'

# 2. Test provider connectivity
curl -X POST "http://localhost:8001/api/v1/coaching/providers/{provider_id}/test"
```
**Expected Response**:
- Returns `status`: `"healthy"` (or `"unreachable"` if local server is down, with exact latency and descriptive message).

---

### Scenario B: Create Philosophy with Manual Context Notes
Create a custom training philosophy and manually inject athletic rules or injury context:
```bash
curl -X POST "http://localhost:8001/api/v1/coaching/philosophies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Polarized Base + Back Protection",
    "target_zone2_pct": 80.0,
    "max_weekly_volume_ramp_pct": 8.0,
    "max_rpe_threshold": 8.0,
    "min_rest_days_per_week": 2,
    "custom_context_notes": "Athlete recovering from lumbar strain. Strictly avoid barbell deadlifts and substitute chest-supported rows. Keep long runs strictly below 80% maximum heart rate."
  }'
```
**Expected Response**:
- Returns saved philosophy with `custom_context_notes` persisted in the database.

---

### Scenario C: Retrospective Workout Critique (Analysis Mode)
Request an AI critique for a completed workout or recent date window:
```bash
curl -X POST "http://localhost:8001/api/v1/coaching/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "workout_session_id": "REPLACE_WITH_WORKOUT_UUID"
  }'
```
**Expected Response**:
- Contains `adherence_score` (e.g. `85.0`), `summary_markdown` critiquing the session against the active philosophy, and concrete `recommendations`.
- Confirms outbound payloads are stripped of athlete personal details and GPS route data.

---

### Scenario D: Forward Schedule Generation (Planning Mode)
Generate a periodized 7-day microcycle tailored to a race target:
```bash
curl -X POST "http://localhost:8001/api/v1/coaching/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "target_goal": "Sub-22 Minute 5k Race Prep",
    "horizon_days": 7,
    "available_days_per_week": 4
  }'
```
**Expected Response**:
- Returns periodized `TrainingSchedulePlan` with array of day-by-day `ScheduledWorkoutItem` records (discipline, duration, target zones, target RPE, exercises, and rest days).
- Obeys user philosophy constraints ($\le 10\%$ volume increase, $\ge 2$ rest days).

---

### Scenario E: Web Coaching Interface
Open your desktop or iPhone Safari browser:
```text
http://localhost:8001/coach
```

**Visual Verification**:
1. **Provider Status Card**: Displays active inference engine (Gemini vs `llama.cpp`) with live latency and health test button.
2. **Philosophy Card**: Shows active philosophy, sliders for Zone 2 % and RPE thresholds, and a textarea to edit/save custom context notes.
3. **Recent Critique Feed**: Renders formatted Markdown critique of the latest workout with adherence badges.
4. **Calendar Microcycle Schedule**: Displays the 7-day or 14-day forward workout schedule with checkboxes to mark planned sessions complete.
