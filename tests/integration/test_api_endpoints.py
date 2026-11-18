"""API integration tests verifying endpoints match contracts/api-ingestion.yaml."""

from datetime import datetime, timezone
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.main import app
from src.models import GPSRoutePoint, HeartRateSample, User, WorkoutSession


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "coach3"


@pytest.mark.asyncio
async def test_auth_url_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_polar = await client.get("/api/v1/integrations/polar/auth-url")
        assert resp_polar.status_code == 200
        assert "auth_url" in resp_polar.json()
        assert "flow.polar.com" in resp_polar.json()["auth_url"]

        resp_c2 = await client.get("/api/v1/integrations/concept2/auth-url")
        assert resp_c2.status_code == 200
        assert "auth_url" in resp_c2.json()
        assert "log.concept2.com" in resp_c2.json()["auth_url"]


@pytest.mark.asyncio
async def test_profile_heart_rate_endpoints(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET default profile
        get_res = await client.get("/api/v1/profile/heart-rate")
        assert get_res.status_code == 200
        profile_data = get_res.json()
        assert "id" in profile_data
        assert profile_data["zone2_min"] == 114

        # PUT updated profile
        update_payload = {
            "resting_hr": 45,
            "max_hr": 195,
            "zone1_min": 98,
            "zone1_max": 117,
            "zone2_min": 117,
            "zone2_max": 136,
            "zone3_min": 136,
            "zone3_max": 156,
            "zone4_min": 156,
            "zone4_max": 175,
            "zone5_min": 175,
            "zone5_max": 195,
        }
        put_res = await client.put("/api/v1/profile/heart-rate", json=update_payload)
        assert put_res.status_code == 200
        updated = put_res.json()
        assert updated["resting_hr"] == 45
        assert updated["zone2_min"] == 117

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_workout_query_and_telemetry_endpoints(db_session: AsyncSession, sample_user):
    user, hr_profile = sample_user
    app.dependency_overrides[get_db] = lambda: db_session

    workout_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    workout = WorkoutSession(
        id=workout_id,
        user_id=user.id,
        provider="polar",
        external_id="api_test_workout_001",
        discipline="outdoor_run",
        title="API Test Run",
        start_time_utc=now,
        local_timezone="UTC",
        total_duration_sec=3600.0,
        active_duration_sec=3600.0,
        total_distance_m=10000.0,
        zone2_duration_sec=1800.0,
        avg_pace_sec_per_km=360.0,
        status="active",
    )
    db_session.add(workout)

    hr = HeartRateSample(
        workout_id=workout_id,
        timestamp_utc=now,
        elapsed_sec=0.0,
        bpm=120,
    )
    db_session.add(hr)

    gps = GPSRoutePoint(
        workout_id=workout_id,
        timestamp_utc=now,
        elapsed_sec=0.0,
        latitude=37.7749,
        longitude=-122.4194,
    )
    db_session.add(gps)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List workouts
        list_res = await client.get("/api/v1/workouts?discipline=outdoor_run")
        assert list_res.status_code == 200
        items = list_res.json()
        assert len(items) >= 1
        assert items[0]["title"] == "API Test Run"
        assert items[0]["zone2_duration_sec"] == 1800.0

        # 2. Detail workout
        detail_res = await client.get(f"/api/v1/workouts/{workout_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["id"] == str(workout_id)

        # 3. Telemetry endpoint
        telem_res = await client.get(f"/api/v1/workouts/{workout_id}/telemetry")
        assert telem_res.status_code == 200
        telem = telem_res.json()
        assert telem["workout_id"] == str(workout_id)
        assert len(telem["heart_rate_samples"]) == 1
        assert len(telem["gps_route_points"]) == 1
        assert telem["heart_rate_samples"][0]["bpm"] == 120
        assert telem["gps_route_points"][0]["latitude"] == 37.7749

    app.dependency_overrides.clear()
