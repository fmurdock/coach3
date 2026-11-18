"""API integration tests for Gym Mode endpoints."""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.main import app
from src.models import StrengthSet, VoiceTranscriptionLog, WorkoutSession


@pytest.mark.asyncio
async def test_parse_gym_transcript_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/gym/parse",
            json={"transcript": "5 sets by 8 reps of back squat at 185 pounds"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence_score"] >= 0.90
        assert len(data["parsed_sets"]) == 1
        item = data["parsed_sets"][0]
        assert item["exercise_name"] == "Barbell Back Squat"
        assert item["sets"] == 5
        assert item["reps"] == 8
        assert item["weight"] == 185.0
        assert item["weight_unit"] == "lbs"


@pytest.mark.asyncio
async def test_list_exercises_api(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/gym/exercises")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) > 0
        names = [item["canonical_name"] for item in items]
        assert "Barbell Back Squat" in names
        assert "Pull-Up" in names


@pytest.mark.asyncio
async def test_get_active_strength_session(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/gym/sessions/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["discipline"] == "strength"


@pytest.mark.asyncio
async def test_commit_strength_sets_and_idempotency(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get or create active session
        sess_resp = await client.get("/api/v1/gym/sessions/active")
        assert sess_resp.status_code == 200
        session_id = sess_resp.json()["id"]

        # 2. Commit 3 sets of bench press
        idem_key = str(uuid.uuid4())
        payload = {
            "idempotency_key": idem_key,
            "raw_transcript": "3 sets of 5 at 225 on bench",
            "confidence_score": 0.95,
            "was_edited": False,
            "sets": [
                {
                    "exercise_name": "Barbell Bench Press",
                    "sets": 3,
                    "reps": 5,
                    "weight": 225.0,
                    "weight_unit": "lbs",
                    "is_bodyweight": False,
                    "added_weight": 0.0,
                }
            ],
        }

        commit_resp = await client.post(
            f"/api/v1/gym/sessions/{session_id}/sets",
            json=payload,
        )
        assert commit_resp.status_code == 201
        created_sets = commit_resp.json()
        assert len(created_sets) == 3
        assert created_sets[0]["reps_completed"] == 5
        assert created_sets[0]["weight"] == 225.0
        assert created_sets[0]["set_index"] == 1
        assert created_sets[1]["set_index"] == 2
        assert created_sets[2]["set_index"] == 3

        # Verify DB directly
        db_q = select(StrengthSet).where(StrengthSet.workout_session_id == uuid.UUID(session_id))
        res = await db_session.execute(db_q)
        all_sets = res.scalars().all()
        assert len(all_sets) == 3

        # Verify voice transcription log created
        log_q = select(VoiceTranscriptionLog).where(VoiceTranscriptionLog.workout_session_id == uuid.UUID(session_id))
        log_res = await db_session.execute(log_q)
        v_log = log_res.scalars().first()
        assert v_log is not None
        assert v_log.raw_transcript == "3 sets of 5 at 225 on bench"

        # 3. Test Idempotency: Submit same payload with same idempotency key
        retry_resp = await client.post(
            f"/api/v1/gym/sessions/{session_id}/sets",
            json=payload,
        )
        assert retry_resp.status_code == 201
        retry_sets = retry_resp.json()
        assert len(retry_sets) == 3

        # Verify set count didn't double
        res2 = await db_session.execute(db_q)
        assert len(res2.scalars().all()) == 3


@pytest.mark.asyncio
async def test_commit_calisthenic_sets_with_added_load(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sess_resp = await client.get("/api/v1/gym/sessions/active")
        session_id = sess_resp.json()["id"]

        parse_resp = await client.post(
            "/api/v1/gym/parse",
            json={"transcript": "3 sets of 12 pullups with an extra 30 pounds added"},
        )
        assert parse_resp.status_code == 200
        stage_data = parse_resp.json()

        commit_resp = await client.post(
            f"/api/v1/gym/sessions/{session_id}/sets",
            json={
                "idempotency_key": str(uuid.uuid4()),
                "raw_transcript": stage_data["raw_transcript"],
                "confidence_score": stage_data["confidence_score"],
                "sets": stage_data["parsed_sets"],
            },
        )
        assert commit_resp.status_code == 201
        saved = commit_resp.json()
        assert len(saved) == 3
        for s in saved:
            assert s["exercise_name"] == "Pull-Up"
            assert s["is_bodyweight"] is True
            assert s["weight"] == 0.0
            assert s["added_weight"] == 30.0


@pytest.mark.asyncio
async def test_commit_sets_with_rpe_and_rest(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sess_resp = await client.get("/api/v1/gym/sessions/active")
        session_id = sess_resp.json()["id"]

        parse_resp = await client.post(
            "/api/v1/gym/parse",
            json={"transcript": "did a heavy single at 315 on deadlift, felt like RPE 8.5, rest 3 minutes"},
        )
        assert parse_resp.status_code == 200
        stage_data = parse_resp.json()

        commit_resp = await client.post(
            f"/api/v1/gym/sessions/{session_id}/sets",
            json={
                "idempotency_key": str(uuid.uuid4()),
                "raw_transcript": stage_data["raw_transcript"],
                "confidence_score": stage_data["confidence_score"],
                "sets": stage_data["parsed_sets"],
            },
        )
        assert commit_resp.status_code == 201
        saved = commit_resp.json()
        assert len(saved) == 1
        s = saved[0]
        assert s["exercise_name"] == "Barbell Deadlift"
        assert s["reps_completed"] == 1
        assert s["weight"] == 315.0
        assert s["rpe"] == 8.5
        assert s["rest_seconds"] == 180


@pytest.mark.asyncio
async def test_commit_multi_exercise_batch_sets(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sess_resp = await client.get("/api/v1/gym/sessions/active")
        session_id = sess_resp.json()["id"]

        parse_resp = await client.post(
            "/api/v1/gym/parse",
            json={"transcript": "3 sets of 10 dumbbell lunges with 50s, followed by 3 sets of 15 calf raises"},
        )
        assert parse_resp.status_code == 200
        stage_data = parse_resp.json()
        assert len(stage_data["parsed_sets"]) == 2

        commit_resp = await client.post(
            f"/api/v1/gym/sessions/{session_id}/sets",
            json={
                "idempotency_key": str(uuid.uuid4()),
                "raw_transcript": stage_data["raw_transcript"],
                "confidence_score": stage_data["confidence_score"],
                "sets": stage_data["parsed_sets"],
            },
        )
        assert commit_resp.status_code == 201
        saved = commit_resp.json()
        assert len(saved) == 6  # 3 lunges + 3 calf raises
        lunge_sets = [s for s in saved if s["exercise_name"] == "Dumbbell Lunge"]
        calf_sets = [s for s in saved if s["exercise_name"] == "Calf Raise"]
        assert len(lunge_sets) == 3
        assert len(calf_sets) == 3


@pytest.mark.asyncio
async def test_gym_ui_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/gym")
        assert resp.status_code == 200
        assert "Coach3 — Gym Mode Voice Logger" in resp.text




