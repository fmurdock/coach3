"""Integration tests for lossless ZIP export, everyday CRUD, preferences, and system diagnostics."""

import csv
from datetime import date, datetime, timedelta, timezone
import io
import json
import uuid
import zipfile

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import encrypt_token
from src.main import app
from src.models.coaching import CoachingPhilosophy, LLMProviderConfig, ScheduledWorkout, TrainingSchedulePlan
from src.models.exercise import StrengthExercise
from src.models.integration import IntegrationAccount, IntegrationClientConfig, SyncAuditLog
from src.models.strength_set import StrengthSet
from src.models.telemetry import GPSRoutePoint, HeartRateSample
from src.models.workout import WorkoutSession
from src.services.seed_service import SeedService


@pytest.mark.asyncio
async def test_export_zip_lossless_excludes_demo_and_secrets(db_session: AsyncSession, sample_user):
    """GET /api/v1/export returns ZIP with backup.json + workouts.csv + strength_sets.csv, zero secrets, and demo isolated."""
    user, _ = sample_user
    user.timezone = "America/Los_Angeles"
    user.passphrase_hash = "super_secret_scrypt_hash_value"

    # Seed encrypted secrets that MUST NOT appear anywhere in export
    db_session.add(
        IntegrationClientConfig(
            provider="polar",
            encrypted_client_id=encrypt_token("polar_secret_client_id"),
            encrypted_client_secret=encrypt_token("polar_secret_client_secret"),
            is_active=True,
        )
    )
    db_session.add(
        IntegrationAccount(
            user_id=user.id,
            provider="polar",
            account_id="p1",
            encrypted_access_token=encrypt_token("polar_secret_access_token"),
            is_active=True,
        )
    )
    db_session.add(
        LLMProviderConfig(
            user_id=user.id,
            provider_type="gemini",
            endpoint_url="https://generativelanguage.googleapis.com",
            api_key_encrypted=encrypt_token("AIzaSy_SECRET_GEMINI_KEY"),
            model_name="gemini-2.5-flash",
            is_active=True,
        )
    )

    # Authentic workout with HR, GPS, and strength set
    now = datetime.now(timezone.utc)
    real_w = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="polar",
        external_id="real-export-1",
        discipline="outdoor_run",
        title="Authentic Morning Run",
        start_time_utc=now - timedelta(days=1),
        total_duration_sec=1800.0,
        active_duration_sec=1800.0,
        total_distance_m=5000.0,
        is_demo=False,
        status="active",
    )
    ex = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Barbell Bench Press",
        slug="barbell-bench-press-export",
        category="barbell",
        primary_muscle_group="chest",
        is_bodyweight=False,
    )
    db_session.add_all([real_w, ex])
    await db_session.flush()

    db_session.add(
        HeartRateSample(workout_id=real_w.id, timestamp_utc=now, elapsed_sec=10.0, bpm=142)
    )
    db_session.add(
        GPSRoutePoint(workout_id=real_w.id, timestamp_utc=now, elapsed_sec=10.0, latitude=47.6, longitude=-122.3, altitude_m=20.0)
    )
    db_session.add(
        StrengthSet(
            workout_session_id=real_w.id,
            exercise_id=ex.id,
            set_index=1,
            reps_completed=5,
            weight=225.0,
            weight_unit="lbs",
            is_warmup=False,
            idempotency_key="exp-s1",
        )
    )
    await db_session.commit()

    # Also seed demo data (is_demo=True) — must be excluded by default!
    await SeedService.seed_sample_workouts(db_session)

    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert "attachment; filename=" in resp.headers.get("content-disposition", "")

        with zipfile.ZipFile(io.BytesIO(resp.content), "r") as zf:
            names = set(zf.namelist())
            assert names == {"backup.json", "workouts.csv", "strength_sets.csv"}

            raw_json_str = zf.read("backup.json").decode("utf-8")
            # Zero secrets leaked!
            for forbidden in (
                "super_secret_scrypt_hash_value",
                "polar_secret_client_id",
                "polar_secret_client_secret",
                "polar_secret_access_token",
                "AIzaSy_SECRET_GEMINI_KEY",
                "api_key_encrypted",
                "encrypted_access_token",
                "passphrase_hash",
            ):
                assert forbidden not in raw_json_str

            backup = json.loads(raw_json_str)
            assert backup["athlete"]["timezone"] == "America/Los_Angeles"
            assert len(backup["workouts"]) == 1  # Demo workouts excluded!
            w_exp = backup["workouts"][0]
            assert w_exp["title"] == "Authentic Morning Run"
            assert len(w_exp["heart_rate_samples"]) == 1
            assert w_exp["heart_rate_samples"][0]["bpm"] == 142
            assert len(w_exp["gps_route_points"]) == 1
            assert len(w_exp["strength_sets"]) == 1

            w_rows = list(csv.DictReader(io.StringIO(zf.read("workouts.csv").decode("utf-8"))))
            assert len(w_rows) == 1
            assert w_rows[0]["title"] == "Authentic Morning Run"

            s_rows = list(csv.DictReader(io.StringIO(zf.read("strength_sets.csv").decode("utf-8"))))
            assert len(s_rows) == 1
            assert s_rows[0]["exercise_name"] == "Barbell Bench Press"


@pytest.mark.asyncio
async def test_everyday_crud_preferences_and_diagnostics(db_session: AsyncSession, sample_user):
    """Tests PATCH workout, DELETE gym set, PATCH scheduled workout, GET/PUT preferences, and GET diagnostics."""
    user, _ = sample_user
    now = datetime.now(timezone.utc)

    # Setup workout, set, philosophy + plan + scheduled workout, and a failed sync audit log
    w = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="coach3_gym",
        external_id="crud-w1",
        discipline="strength",
        title="Original Title",
        user_notes="Initial notes",
        start_time_utc=now,
        total_duration_sec=1800.0,
        active_duration_sec=1800.0,
    )
    ex = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Barbell Back Squat",
        slug="squat-crud-test",
        category="barbell",
        primary_muscle_group="quadriceps",
        is_bodyweight=False,
    )
    phil = CoachingPhilosophy(
        id=uuid.uuid4(),
        user_id=user.id,
        name="CRUD Phil",
        is_active=True,
    )
    db_session.add_all([w, ex, phil])
    await db_session.flush()

    s_row = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=w.id,
        exercise_id=ex.id,
        set_index=1,
        reps_completed=5,
        weight=275.0,
        weight_unit="lbs",
        idempotency_key="crud-set-1",
    )
    plan = TrainingSchedulePlan(
        id=uuid.uuid4(),
        user_id=user.id,
        philosophy_id=phil.id,
        target_goal="10k PR",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=6),
        horizon_days=7,
        summary_markdown="Plan summary",
        status="active",
    )
    db_session.add_all([s_row, plan])
    await db_session.flush()

    sw = ScheduledWorkout(
        id=uuid.uuid4(),
        plan_id=plan.id,
        target_date=date.today(),
        discipline="outdoor_run",
        title="Zone 2 Easy Run",
        planned_duration_min=45,
        is_completed=False,
    )
    failed_sync = SyncAuditLog(
        user_id=user.id,
        provider="polar",
        trigger_type="manual",
        status="failed",
        error_message="Upstream 503",
        started_at=now,
        completed_at=now,
    )
    db_session.add_all([sw, failed_sync])
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. PATCH /api/v1/workouts/{id}
        r_patch_w = await client.patch(
            f"/api/v1/workouts/{w.id}",
            json={"title": "Updated Push/Leg Title", "user_notes": "Felt strong today"},
        )
        assert r_patch_w.status_code == 200
        assert r_patch_w.json()["title"] == "Updated Push/Leg Title"
        assert r_patch_w.json()["user_notes"] == "Felt strong today"

        # 2. DELETE /api/v1/gym/sets/{id}
        r_del_s = await client.delete(f"/api/v1/gym/sets/{s_row.id}")
        assert r_del_s.status_code == 204
        assert (await db_session.execute(select(StrengthSet).where(StrengthSet.id == s_row.id))).scalar_one_or_none() is None

        # 3. PATCH /api/v1/coaching/scheduled-workouts/{id}
        r_sw = await client.patch(
            f"/api/v1/coaching/scheduled-workouts/{sw.id}",
            json={"is_completed": True},
        )
        assert r_sw.status_code == 200
        assert r_sw.json()["is_completed"] is True

        # 4. GET / PUT /api/v1/profile/preferences
        r_pref_get = await client.get("/api/v1/profile/preferences")
        assert r_pref_get.status_code == 200
        assert r_pref_get.json()["timezone"] == "UTC"

        r_pref_bad = await client.put("/api/v1/profile/preferences", json={"timezone": "Not/A_Zone"})
        assert r_pref_bad.status_code == 422

        r_pref_ok = await client.put("/api/v1/profile/preferences", json={"timezone": "America/New_York"})
        assert r_pref_ok.status_code == 200
        assert r_pref_ok.json()["timezone"] == "America/New_York"

        # 5. GET /api/v1/system/diagnostics
        r_diag = await client.get("/api/v1/system/diagnostics")
        assert r_diag.status_code == 200
        diag = r_diag.json()
        assert diag["database_ok"] is True
        assert diag["has_recent_sync_failures"] is True
        assert len(diag["recent_sync_logs"]) == 1
        assert diag["recent_sync_logs"][0]["status"] == "failed"
