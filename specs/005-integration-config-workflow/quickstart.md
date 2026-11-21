# Quickstart & Verification Scenarios: Integration Configuration & Workflow

**Feature**: `005-integration-config-workflow`  
**Date**: 2026-11-18  
**Status**: Ready for Verification  

This quickstart guides you through verifying the new Configuration hub, Polar & Concept2 credential persistence, connection diagnostics, demo data seeding, and cross-module navigation.

---

## 1. Environment & Setup

Ensure the server is running on port 8000 (or 8001):
```bash
source .venv/bin/activate
uvicorn src.main:app --port 8000 --reload
```

---

## 2. Verification Scenarios

### Scenario A: Save & Verify Polar Developer Credentials
1. Navigate to `http://localhost:8000/config`.
2. Locate the **Polar AccessLink** setup card:
   - Note the dynamically computed OAuth Callback URI (e.g. `http://localhost:8000/api/v1/integrations/polar/callback`).
   - Click "Copy Redirect URI" to paste into Polar Flow Developer Portal.
3. Enter your Polar `Client ID` and `Client Secret`, then click **Save Credentials**.
4. Test API verification:
```bash
curl -X POST "http://localhost:8000/api/v1/integrations/polar/verify"
```
**Expected Outcome**: Returns connection status (e.g. `healthy` or `unconfigured`/`expired`), athlete identity, and token expiration window.

---

### Scenario B: Save & Verify Concept2 Credentials
1. On `http://localhost:8000/config`, locate the **Concept2 Logbook** setup card.
2. Enter your Concept2 `Client ID` and `Client Secret`, then click **Save Credentials**.
3. Click **Connect Concept2** to launch the OAuth approval flow.
4. After approval, verify the browser redirects back to `http://localhost:8000/config?status=connected&provider=concept2` with a green success toast.
5. Click **Verify Connection** and verify the athlete username and active token badge appear.

---

### Scenario C: One-Click Demo Workout Seeding
1. On `http://localhost:8000/config`, scroll to the **Demo & Testing Tools** card.
2. Click **Load Sample Workouts** (or run `python -m src.scripts.seed_demo` via terminal).
3. Navigate to `http://localhost:8000/dashboard` via the top navigation bar.
4. Verify that:
   - Weekly Zone 2 hours and total mileage display populated numbers.
   - Outdoor running and Concept2 rowing sessions appear in the activity feed.
   - Peak PRs (e.g. 5k run pace, 500m row split, bench press 1RM) are plotted.
5. Navigate to `http://localhost:8000/coach` and click **Analyze Recent Workouts** to verify the AI coach evaluates the seeded sessions.

---

### Scenario D: Safe Demo Reset
1. Return to `http://localhost:8000/config`.
2. Click **Reset Demo Data** (or send `DELETE /api/v1/admin/demo`).
3. Verify that only demo sessions (`is_demo = true`) are removed, while your saved Polar/Concept2 credentials and real accounts remain completely intact.

---

### Scenario E: Unified Cross-Module Navigation
1. Open `http://localhost:8000/gym`.
2. Verify the top navbar renders tabs: **Gym Mode**, **Volume Dashboard**, **AI Coach**, and **Settings**.
3. Tap each tab and verify instantaneous navigation without broken styles or layout shifts across mobile Safari and desktop browsers.
