"""API integration tests for Adaptive AI Coaching endpoints."""

from datetime import datetime, timedelta, timezone
import json
import uuid
import httpx
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.main import app
from src.models import WorkoutSession
from src.models.coaching import LLMProviderConfig
from src.services.llm_client import BaseLLMClient
import src.api.coaching as coaching_api


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_coach_ui_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/coach")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        text = resp.text
        assert "AI Coach" in text
        assert "Data Sovereignty Active" in text
        assert "Workout Critique" in text
        assert "Training Plan" in text


@pytest.mark.asyncio
async def test_provider_management_api(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List providers initially (empty)
        resp = await client.get("/api/v1/coaching/providers")
        assert resp.status_code == 200
        providers = resp.json()
        assert len(providers) == 0

        # 2. Save Gemini provider
        gemini_payload = {
            "provider_type": "gemini",
            "endpoint_url": "https://generativelanguage.googleapis.com",
            "api_key": "AIzaSyTestKey123",
            "model_name": "gemini-2.5-flash",
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        resp = await client.post("/api/v1/coaching/providers", json=gemini_payload)
        assert resp.status_code == 200
        gemini_data = resp.json()
        assert gemini_data["provider_type"] == "gemini"
        assert gemini_data["is_active"] is True
        assert gemini_data["has_api_key"] is True
        gemini_id = gemini_data["id"]

        # 3. Save llama.cpp provider
        llama_payload = {
            "provider_type": "llama_cpp",
            "endpoint_url": "http://localhost:8080/v1",
            "model_name": "qwen2.5-14b-instruct",
            "temperature": 0.5,
            "max_tokens": 2048,
        }
        resp = await client.post("/api/v1/coaching/providers", json=llama_payload)
        assert resp.status_code == 200
        llama_data = resp.json()
        assert llama_data["provider_type"] == "llama_cpp"
        assert llama_data["is_active"] is False
        llama_id = llama_data["id"]

        # 4. Activate llama.cpp provider
        resp = await client.post(f"/api/v1/coaching/providers/{llama_id}/activate")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

        # Verify Gemini is now inactive
        resp = await client.get("/api/v1/coaching/providers")
        providers = resp.json()
        g = next(p for p in providers if p["id"] == gemini_id)
        l = next(p for p in providers if p["id"] == llama_id)
        assert g["is_active"] is False
        assert l["is_active"] is True


@pytest.mark.asyncio
async def test_philosophy_management_api(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List philosophies (seeds 4 default presets)
        resp = await client.get("/api/v1/coaching/philosophies")
        assert resp.status_code == 200
        phils = resp.json()
        assert len(phils) == 4
        assert phils[0]["is_active"] is True

        # 2. Save custom philosophy with manual context notes
        custom_payload = {
            "name": "Marathon Base + Knee Rehab",
            "description": "High Zone 2 with strict quad dominance avoidance",
            "target_zone2_pct": 85.0,
            "max_weekly_volume_ramp_pct": 8.0,
            "max_rpe_threshold": 8.0,
            "min_rest_days_per_week": 2,
            "primary_modality": "endurance",
            "custom_context_notes": "Athlete recovering from runner's knee. Substitute Bulgarian split squats for back squats.",
        }
        resp = await client.post("/api/v1/coaching/philosophies", json=custom_payload)
        assert resp.status_code == 200
        custom_phil = resp.json()
        assert custom_phil["name"] == "Marathon Base + Knee Rehab"
        assert "runner's knee" in custom_phil["custom_context_notes"]

        # 3. Activate custom philosophy
        resp = await client.post(f"/api/v1/coaching/philosophies/{custom_phil['id']}/activate")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_analyze_and_plan_api(db_session: AsyncSession, sample_user, monkeypatch):
    user, _ = sample_user
    app.dependency_overrides[get_db] = lambda: db_session

    now = datetime.now(timezone.utc)
    # Add a workout session
    ws = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="polar",
        external_id="polar-critique-api",
        discipline="outdoor_run",
        title="12k Base Aerobic Run",
        start_time_utc=now - timedelta(hours=4),
        total_duration_sec=4200.0,
        active_duration_sec=4200.0,
        total_distance_m=12000.0,
        zone1_duration_sec=600.0,
        zone2_duration_sec=3300.0,
        zone3_duration_sec=300.0,
        avg_pace_sec_per_km=350.0,
    )
    db_session.add(ws)

    # Configure active provider
    prov = LLMProviderConfig(
        id=uuid.uuid4(),
        user_id=user.id,
        provider_type="llama_cpp",
        endpoint_url="http://localhost:8080/v1",
        model_name="qwen2.5-14b-instruct",
        is_active=True,
    )
    db_session.add(prov)
    await db_session.commit()

    # Mock CoachingService LLM generation
    class MockServiceLLM(BaseLLMClient):
        async def test_connection(self):
            pass

        async def generate_structured(self, system_prompt: str, user_prompt: str) -> str:
            if "EVALUATION CRITERIA" in system_prompt:
                return json.dumps({
                    "adherence_score": 88.5,
                    "summary_markdown": "### Great Aerobic Discipline\nStrict adherence to Zone 2 with minimal cardiac drift.",
                    "adherence_details": {"zone2_pct": 78.5, "target": 80.0},
                    "strain_assessment": {"neuromuscular_fatigue": "low"},
                    "recommendations": ["Active recovery walk tomorrow", "Adequate protein intake"]
                })
            else:
                return json.dumps({
                    "summary_markdown": "### 7-Day Progressive Microcycle\nVolume ramp capped under 10%.",
                    "workouts": [
                        {
                            "day_offset": 0,
                            "discipline": "outdoor_run",
                            "title": "Zone 2 Base Run",
                            "planned_duration_min": 50,
                            "target_distance_m": 8000.0,
                            "target_zone": "Zone 2",
                            "target_rpe": 5.0,
                            "notes": "Flat path",
                        },
                        {
                            "day_offset": 1,
                            "discipline": "rest",
                            "title": "Rest & Mobility",
                            "planned_duration_min": 0,
                            "target_rpe": 1.0,
                            "notes": "Full rest",
                        }
                    ]
                })

    mock_client = MockServiceLLM()
    async def mock_get_active_llm_client(session, user_id):
        return mock_client, "llama_cpp"

    monkeypatch.setattr(
        coaching_api.coaching_service,
        "get_active_llm_client",
        mock_get_active_llm_client,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test Analysis Mode
        resp = await client.post("/api/v1/coaching/analyze", json={"workout_session_id": str(ws.id)})
        assert resp.status_code == 200
        critique = resp.json()
        assert critique["adherence_score"] == 88.5
        assert "Great Aerobic Discipline" in critique["summary_markdown"]
        assert len(critique["recommendations"]) == 2

        # Test Recent Critiques
        resp_critiques = await client.get("/api/v1/coaching/critiques/recent")
        assert resp_critiques.status_code == 200
        assert len(resp_critiques.json()) >= 1

        # Test Planning Mode
        plan_req = {
            "target_goal": "Sub 1:40 Half Marathon",
            "horizon_days": 7,
            "available_days_per_week": 5,
        }
        resp = await client.post("/api/v1/coaching/plan", json=plan_req)
        assert resp.status_code == 200
        plan = resp.json()
        assert plan["target_goal"] == "Sub 1:40 Half Marathon"
        assert len(plan["scheduled_workouts"]) == 2
        assert plan["scheduled_workouts"][0]["discipline"] == "outdoor_run"

        # Test Active Plan Retrieval
        resp = await client.get("/api/v1/coaching/plans/active")
        assert resp.status_code == 200
        active_plan = resp.json()
        assert active_plan["id"] == plan["id"]
        assert active_plan["status"] == "active"
