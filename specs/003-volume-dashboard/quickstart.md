# Quickstart & Verification Scenarios: Volume Modeling & Performance Dashboard

**Feature**: `003-volume-dashboard`  
**Date**: 2026-11-17  
**Status**: Ready for Verification

This quickstart guides you through validating the volume modeling queries, Zone 2 distributions, 1RM Epley calculations, endurance milestone PR detections, and the visual dashboard.

---

## 1. Environment & Setup

Ensure the server is running on port 8001:
```bash
.venv/bin/uvicorn src.main:app --port 8001 --reload
```

---

## 2. Verification Scenarios

### Scenario A: Unified Volume Summary (30-Day Window)
**API Call**:
```bash
curl -X GET "http://localhost:8001/api/v1/analytics/summary?window=30d"
```

**Expected JSON Response**:
- `total_duration_hours`: Combined hours of cardio + strength.
- `zone2_duration_hours`: Aggregate duration in Zone 2.
- `zone2_percentage`: Ratio of Zone 2 time to total cardio time.
- `total_cardio_distance_miles`: Total miles from outdoor runs and erg sessions.
- `total_strength_volume_lbs`: Total volume load ($\sum \text{sets} \times \text{reps} \times \text{weight}$).
- `effective_working_sets`: Working sets count (excluding warmups).

---

### Scenario B: Strength Muscle Group Breakdown
**API Call**:
```bash
curl -X GET "http://localhost:8001/api/v1/analytics/strength?window=30d"
```

**Expected JSON Response**:
- `muscle_group_sets`: Map of working sets per muscle group (e.g. `{"chest": 12, "quadriceps": 15}`).
- `muscle_group_volume`: Tonnage load grouped by primary muscle group.
- `added_calisthenic_load_lbs`: Isolated external load added to pull-ups/dips.

---

### Scenario C: Personal Record (PR) Showcase & Epley 1RM
**API Call**:
```bash
curl -X GET "http://localhost:8001/api/v1/analytics/prs?window=all"
```

**Expected JSON Response**:
- Contains exercise PR items with `estimated_1rm` evaluated via Epley formula ($w \times (1 + r/30)$).
- Contains endurance PRs (fastest 5k pace, best 500m erg split).

---

### Scenario D: Web Dashboard Interface
Open your browser or iPhone Safari:
```text
http://localhost:8001/dashboard
```

**Visual Verification**:
1. Top KPI Summary Tiles: Total Training Time, Zone 2 Hours, Running Mileage, Erg Meters, Total Volume Load, Working Sets.
2. Weekly Mileage & Volume Chart: Interactive bars rendered via local Chart.js.
3. Polarized Zone Doughnut: Zone 1–5 distribution highlighting Zone 2.
4. Muscle Group Sets Bar Chart: Horizontal bars showing effective sets.
5. PR Trophy Showcase: Badges of all-time best lifts and cardio milestones.
6. Filter Pills: Tapping `7D`, `30D`, `90D`, `YTD`, or `All Time` reloads the charts instantly.
