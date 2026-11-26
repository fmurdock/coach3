"""Real PostgreSQL Alembic migration round-trip & constraint verification tests.

Gated by TEST_DATABASE_URL (e.g. postgresql+asyncpg://coach3:coach3@127.0.0.1:5432/coach3_test).
Skipped automatically when TEST_DATABASE_URL is not configured.
"""

from datetime import datetime, timezone
import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.adapters.base import NormalizedWorkout
from src.models.coaching import CoachingPhilosophy, LLMProviderConfig
from src.models.user import User, UserHeartRateProfile
from src.services.ingestion import ingest_workout

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL or not TEST_DB_URL.startswith("postgresql"),
    reason="Set TEST_DATABASE_URL=postgresql+asyncpg://... to run real PostgreSQL migration tests",
)


def _run_alembic(*args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DB_URL
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"alembic {' '.join(args)} failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"


@pytest.mark.asyncio
async def test_postgres_alembic_roundtrip_constraints_and_on_conflict():
    """Verify upgrade head -> downgrade base -> upgrade head, partial unique indexes, HR checks, and ON CONFLICT upserts."""
    # 1. Round-trip migrations cleanly
    _run_alembic("upgrade", "head")
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", "head")

    engine = create_async_engine(TEST_DB_URL, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with Session() as db:
            user = User(id=uuid.uuid4(), timezone="America/Los_Angeles")
            db.add(user)
            await db.commit()

            # 2. Partial unique index on active LLMProviderConfig (two active must fail; two inactive allowed)
            p1 = LLMProviderConfig(
                user_id=user.id,
                provider_type="gemini",
                endpoint_url="https://generativelanguage.googleapis.com",
                model_name="gemini-2.5-flash",
                is_active=True,
            )
            db.add(p1)
            await db.commit()

            p2 = LLMProviderConfig(
                user_id=user.id,
                provider_type="llama_cpp",
                endpoint_url="http://localhost:8080/v1",
                model_name="qwen2.5",
                is_active=True,
            )
            db.add(p2)
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()

            # 3. Partial unique index on active CoachingPhilosophy
            ph1 = CoachingPhilosophy(user_id=user.id, name="P1", is_active=True)
            db.add(ph1)
            await db.commit()

            ph2 = CoachingPhilosophy(user_id=user.id, name="P2", is_active=True)
            db.add(ph2)
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()

            # 4. HR profile check constraint (resting_hr < 25 fails)
            bad_hr = UserHeartRateProfile(
                user_id=user.id,
                resting_hr=20,
                max_hr=185,
                zone1_min=90,
                zone1_max=110,
                zone2_min=110,
                zone2_max=130,
                zone3_min=130,
                zone3_max=150,
                zone4_min=150,
                zone4_max=170,
                zone5_min=170,
                zone5_max=185,
            )
            db.add(bad_hr)
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()

            # 5. PostgreSQL ON CONFLICT (provider, external_id) DO UPDATE upsert
            nw = NormalizedWorkout(
                provider="polar",
                external_id="pg-upsert-1",
                discipline="outdoor_run",
                title="Initial PG Run",
                start_time_utc=datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc),
                local_timezone="UTC",
                total_duration_sec=1800.0,
                active_duration_sec=1800.0,
                total_distance_m=5000.0,
            )
            w1, created1 = await ingest_workout(db, user.id, nw, None)
            await db.commit()
            assert created1 is True

            nw.total_calories = 555
            w2, created2 = await ingest_workout(db, user.id, nw, None)
            await db.commit()
            assert created2 is False
            assert w2.id == w1.id
            assert w2.total_calories == 555
    finally:
        await engine.dispose()
