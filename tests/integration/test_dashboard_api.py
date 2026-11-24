"""Integration tests for Macro Dashboard endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.main import app
from src.services.seed_service import SeedService


@pytest.mark.asyncio
async def test_get_dashboard_macro_endpoint(db_session: AsyncSession):
    # Seed standard demo workouts
    await SeedService.seed_sample_workouts(db_session)

    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/analytics/dashboard?window=30d")
        assert resp.status_code == 200
        data = resp.json()

        assert "cardio" in data
        assert "resistance" in data
        assert data["cardio"]["total_cardio_minutes"] > 0
        assert data["cardio"]["zone2_minutes"] > 0
        assert data["cardio"]["zone4_minutes"] > 0
        assert data["cardio"]["zone5_minutes"] > 0
        assert data["cardio"]["zone2_weekly_goal_minutes"] == 120.0
        assert data["cardio"]["vo2max_weekly_goal_minutes"] == 20.0
        assert len(data["cardio"]["weekly_trend"]) > 0
        assert "zone2_minutes" in data["cardio"]["weekly_trend"][0]
        assert "zone4_minutes" in data["cardio"]["weekly_trend"][0]

        resistance = data["resistance"]
        cat_slugs = [m["muscle_group"] for m in resistance]
        assert cat_slugs == ["push", "pull", "legs", "abs"]
        for cat in resistance:
            assert cat["weekly_goal_sets"] == 10.0
            assert cat["working_sets"] > 0
            assert cat["top_weight_lbs"] is not None

        # 1b. Test custom start_date / end_date filtering on macro + workouts endpoints
        from datetime import date, timedelta
        today = date.today()
        d_start = (today - timedelta(days=1)).isoformat()
        d_end = today.isoformat()
        resp_custom_macro = await client.get(f"/api/v1/analytics/dashboard?start_date={d_start}&end_date={d_end}")
        assert resp_custom_macro.status_code == 200
        resp_custom_w = await client.get(f"/api/v1/workouts?start_date={d_start}&end_date={d_end}")
        assert resp_custom_w.status_code == 200
        assert len(resp_custom_w.json()) >= 1

        # 2. Test /api/v1/workouts returns highlight metrics
        resp_w = await client.get("/api/v1/workouts?limit=10")
        assert resp_w.status_code == 200
        workouts = resp_w.json()
        assert len(workouts) > 0
        for w in workouts:
            assert "primary_metric_label" in w
            assert "has_telemetry" in w
            assert "is_interval_workout" in w

        # 2b. Test strength session detail returns user_notes, strength_sets, and empty time_series (no blank chart)
        strength_row = next((w for w in workouts if w["discipline"] == "strength"), None)
        assert strength_row is not None
        assert strength_row["has_telemetry"] is False
        resp_str_detail = await client.get(f"/api/v1/workouts/{strength_row['id']}/detail")
        assert resp_str_detail.status_code == 200
        str_detail = resp_str_detail.json()
        assert str_detail["user_notes"] is not None
        assert len(str_detail["strength_sets"]) == 7
        assert str_detail["time_series"] == []

        # 3. Test /api/v1/workouts/{id}/detail
        interval_row = next((w for w in workouts if w["is_interval_workout"]), None)
        assert interval_row is not None
        resp_detail = await client.get(f"/api/v1/workouts/{interval_row['id']}/detail")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["workout_id"] == interval_row["id"]
        assert len(detail["splits"]) > 0
        assert detail["interval_consistency"] is not None
        assert len(detail["interval_consistency"]["superimposed_curves"]) > 0

        # 4. Test GPX upload attaches route_points to outdoor run
        run_row = next((w for w in workouts if w["discipline"] == "outdoor_run"), None)
        assert run_row is not None
        gpx_payload = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1"><trk><trkseg>
  <trkpt lat="47.6730" lon="-122.0280"><ele>15.0</ele></trkpt>
  <trkpt lat="47.6738" lon="-122.0285"><ele>19.0</ele></trkpt>
</trkseg></trk></gpx>"""
        gpx_resp = await client.post(f"/api/v1/workouts/{run_row['id']}/gpx", json={"gpx_xml": gpx_payload})
        assert gpx_resp.status_code == 200
        gpx_detail = gpx_resp.json()
        assert len(gpx_detail["route_points"]) == 2
        assert gpx_detail["route_points"][0]["latitude"] == 47.6730
        assert gpx_detail["route_points"][1]["longitude"] == -122.0285

        # 5. Test HR profile default is 185 bpm and PUT updates zones + recalculates
        hr_get = await client.get("/api/v1/profile/heart-rate")
        assert hr_get.status_code == 200
        assert hr_get.json()["max_hr"] == 185

        hr_resp = await client.put(
            "/api/v1/profile/heart-rate",
            json={
                "resting_hr": 55,
                "max_hr": 185,
                "zone1_min": 93,
                "zone1_max": 111,
                "zone2_min": 111,
                "zone2_max": 130,
                "zone3_min": 130,
                "zone3_max": 148,
                "zone4_min": 148,
                "zone4_max": 167,
                "zone5_min": 167,
                "zone5_max": 185,
            },
        )
        assert hr_resp.status_code == 200
        assert hr_resp.json()["max_hr"] == 185

        # 6. Verify /dashboard serves updated UI with no-cache headers
        html_resp = await client.get("/dashboard")
        assert html_resp.status_code == 200
        assert "no-cache" in html_resp.headers.get("cache-control", "")
        assert "renderRouteMapCard" in html_resp.text
        assert "renderSessionSummaryAndZones" in html_resp.text
        assert "renderStrengthSetsSection" in html_resp.text
        assert "zone2MacroChart" in html_resp.text
        assert "vo2MacroChart" in html_resp.text
        assert "filter-start-date" in html_resp.text
        assert "Workout Graph:" in html_resp.text

    app.dependency_overrides.pop(get_db, None)
