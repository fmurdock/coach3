"""API integration tests for Volume Dashboard and Analytics endpoints."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.main import app
from src.models import WorkoutSession
from src.models.exercise import StrengthExercise
from src.models.strength_set import StrengthSet


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_ui_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        text = resp.text
        assert "Volume Dashboard" in text
        assert "chart.umd.js" in text
        assert "kpi-grid" in text


@pytest.mark.asyncio
async def test_cardio_analytics_api(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    app.dependency_overrides[get_db] = lambda: db_session
    now = datetime.now(timezone.utc)

    # Ingest 1 run and 1 row session
    run = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="polar",
        external_id="polar-test-run",
        discipline="outdoor_run",
        title="10k Tempo Run",
        start_time_utc=now - timedelta(days=4),
        total_duration_sec=3000.0,
        active_duration_sec=3000.0,
        total_distance_m=10000.0,
        zone1_duration_sec=200.0,
        zone2_duration_sec=2400.0,
        zone3_duration_sec=400.0,
        avg_pace_sec_per_km=300.0,
    )
    row = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="concept2",
        external_id="c2-test-row",
        discipline="indoor_row",
        title="2k Erg Benchmark",
        start_time_utc=now - timedelta(days=2),
        total_duration_sec=420.0,
        active_duration_sec=420.0,
        total_distance_m=2000.0,
        zone2_duration_sec=300.0,
        avg_split_sec_per_500m=105.0,
    )
    db_session.add_all([run, row])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Default 30d window
        resp = await client.get("/api/v1/analytics/cardio?window=30d")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_distance_km"] == 12.0
        assert data["outdoor_run_km"] == 10.0
        assert data["erg_row_meters"] == 2000.0
        assert data["zone2_duration_hours"] > 0
        assert "zone2" in data["zone_distribution_hours"]
        assert len(data["weekly_trend"]) >= 1


@pytest.mark.asyncio
async def test_strength_analytics_api(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    app.dependency_overrides[get_db] = lambda: db_session
    now = datetime.now(timezone.utc)

    # Session
    sess = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="manual_gym",
        external_id=f"gym-{uuid.uuid4()}",
        discipline="strength",
        title="Chest & Core",
        start_time_utc=now - timedelta(days=1),
        total_duration_sec=2700.0,
        active_duration_sec=2400.0,
    )
    db_session.add(sess)

    # Exercise
    bench = StrengthExercise(
        id=uuid.uuid4(),
        canonical_name="Barbell Bench Press",
        slug="barbell-bench-press",
        category="barbell",
        primary_muscle_group="chest",
        is_bodyweight=False,
    )
    db_session.add(bench)
    await db_session.flush()

    # Sets
    s1 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=sess.id,
        exercise_id=bench.id,
        set_index=1,
        reps_completed=10,
        weight=135.0,
        weight_unit="lbs",
        is_warmup=True,  # warmup
        idempotency_key=f"bench-warm-{uuid.uuid4()}",
    )
    s2 = StrengthSet(
        id=uuid.uuid4(),
        workout_session_id=sess.id,
        exercise_id=bench.id,
        set_index=2,
        reps_completed=8,
        weight=185.0,
        weight_unit="lbs",
        is_warmup=False,  # 8 * 185 = 1480 lbs
        idempotency_key=f"bench-work-{uuid.uuid4()}",
    )
    db_session.add_all([s1, s2])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/analytics/strength?window=30d")
        assert resp.status_code == 200
        data = resp.json()

        assert data["effective_working_sets"] == 1
        assert data["total_volume_load_lbs"] == 1480.0
        assert data["muscle_group_sets"].get("chest") == 1


@pytest.mark.asyncio
async def test_unified_summary_and_prs_api(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    app.dependency_overrides[get_db] = lambda: db_session
    now = datetime.now(timezone.utc)

    # Ingest 5k run
    run5k = WorkoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="polar",
        external_id="polar-5k-pr",
        discipline="outdoor_run",
        title="5k PR Race",
        start_time_utc=now - timedelta(days=3),
        total_duration_sec=1260.0,
        active_duration_sec=1260.0,
        total_distance_m=5000.0,
        zone2_duration_sec=800.0,
        avg_pace_sec_per_km=252.0,
    )
    db_session.add(run5k)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Summary
        sum_resp = await client.get("/api/v1/analytics/summary?window=30d")
        assert sum_resp.status_code == 200
        summary = sum_resp.json()
        assert "start_date" in summary
        assert "end_date" in summary
        assert summary["total_duration_hours"] > 0
        assert summary["total_cardio_distance_miles"] > 0

        # 2. PRs
        prs_resp = await client.get("/api/v1/analytics/prs?window=all")
        assert prs_resp.status_code == 200
        prs = prs_resp.json()
        assert len(prs) >= 1
        pr_5k = next((p for p in prs if p["milestone_type"] == "5k"), None)
        assert pr_5k is not None
        assert "5k Run" in pr_5k["title"]
        assert pr_5k["is_recent"] is True

        # Discipline filter
        prs_run_only = (await client.get("/api/v1/analytics/prs?discipline=outdoor_run")).json()
        assert all(p["discipline"] == "outdoor_run" for p in prs_run_only)
