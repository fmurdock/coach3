# Quickstart & Verification Scenarios: Gym Mode Voice Logging

**Feature**: `002-gym-voice-logging`  
**Date**: 2026-11-17  
**Status**: Ready for Verification

This quickstart guides you through validating the natural language parsing engine, staging flow, exercise taxonomy, and atomic set persistence.

---

## 1. Environment & Setup

Ensure the virtual environment is active and database migrations are applied:
```bash
source .venv/bin/activate
alembic upgrade head
```

Run the seed script to populate canonical strength exercises and aliases:
```bash
python -m src.scripts.seed_exercises
```

---

## 2. Verification Scenarios

### Scenario A: Compound Barbell Lift Dictation
**Input Transcript**: `"5 sets by 8 reps of back squat at 185 pounds"`

**API Call**:
```bash
curl -X POST http://localhost:8001/api/v1/gym/parse \
  -H "Content-Type: application/json" \
  -d '{"transcript": "5 sets by 8 reps of back squat at 185 pounds"}'
```

**Expected JSON Response**:
- `parsed_sets[0].exercise_name`: `"Barbell Back Squat"`
- `parsed_sets[0].sets`: `5`
- `parsed_sets[0].reps`: `8`
- `parsed_sets[0].weight`: `185.0`
- `parsed_sets[0].weight_unit`: `"lbs"`
- `parsed_sets[0].is_bodyweight`: `false`
- `parsed_sets[0].added_weight`: `0.0`
- `confidence_score`: `> 0.90`

---

### Scenario B: Weighted Calisthenic Dictation
**Input Transcript**: `"3 sets of 12 pullups with an extra 30 pounds added"`

**API Call**:
```bash
curl -X POST http://localhost:8001/api/v1/gym/parse \
  -H "Content-Type: application/json" \
  -d '{"transcript": "3 sets of 12 pullups with an extra 30 pounds added"}'
```

**Expected JSON Response**:
- `parsed_sets[0].exercise_name`: `"Pull-Up"`
- `parsed_sets[0].sets`: `3`
- `parsed_sets[0].reps`: `12`
- `parsed_sets[0].is_bodyweight`: `true`
- `parsed_sets[0].added_weight`: `30.0`
- `confidence_score`: `> 0.90`

---

### Scenario C: Shorthand Plate Math & RPE
**Input Transcript**: `"did 3 reps on deadlift at two plates felt like RPE 8.5"`

**API Call**:
```bash
curl -X POST http://localhost:8001/api/v1/gym/parse \
  -H "Content-Type: application/json" \
  -d '{"transcript": "did 3 reps on deadlift at two plates felt like RPE 8.5"}'
```

**Expected JSON Response**:
- `parsed_sets[0].exercise_name`: `"Barbell Deadlift"`
- `parsed_sets[0].sets`: `1`
- `parsed_sets[0].reps`: `3`
- `parsed_sets[0].weight`: `225.0`
- `parsed_sets[0].rpe`: `8.5`

---

### Scenario D: Committing Confirmed Sets (Atomic Database Write)
**API Call**:
```bash
SESSION_ID=$(curl -s http://localhost:8001/api/v1/gym/sessions/active | jq -r .id)

curl -X POST "http://localhost:8001/api/v1/gym/sessions/${SESSION_ID}/sets" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "c71a39f6-0617-48f5-bfa3-bb6dc72c219a",
    "raw_transcript": "5 sets by 8 reps of back squat at 185 pounds",
    "was_edited": false,
    "sets": [
      {
        "exercise_id": "...",
        "exercise_name": "Barbell Back Squat",
        "sets": 5,
        "reps": 8,
        "weight": 185.0,
        "weight_unit": "lbs",
        "is_bodyweight": false,
        "added_weight": 0.0,
        "rpe": null
      }
    ]
  }'
```

**Verification**:
- Returns HTTP `201 Created` with an array of 5 created `strength_sets` (set_index 1 through 5).
- Resending the exact same `idempotency_key` returns the identical 5 sets without creating duplicates.
