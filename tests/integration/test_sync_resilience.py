"""Integration tests for lossless sync, pagination, retries, rollback, soft-sync, isolation, and orphan recovery."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.adapters.base import NormalizedHeartRateSample, NormalizedWorkout, SyncBatchResult
from src.core.http_client import request_with_retry
from src.core.scheduler import _run_isolated_sync_pass, recover_orphaned_sync_logs
from src.core.security import encrypt_token
from src.models.integration import IntegrationAccount, SyncAuditLog
from src.models.user import User, UserHeartRateProfile
from src.models.workout import WorkoutSession
from src.services.ingestion import ingest_workout
from src.services.sync_service import run_sync_for_account


def _make_workout(ext_id: str, provider: str = "polar", with_hr: bool = True) -> NormalizedWorkout:
    start = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
    hrs = (
        [
            NormalizedHeartRateSample(
                elapsed_sec=float(i),
                bpm=130,
                timestamp_utc=start + timedelta(seconds=i),
            )
            for i in range(60)
        ]
        if with_hr
        else []
    )
    return NormalizedWorkout(
        provider=provider,
        external_id=ext_id,
        discipline="outdoor_run",
        title=f"Workout {ext_id}",
        start_time_utc=start,
        local_timezone="UTC",
        total_duration_sec=1800.0,
        active_duration_sec=1800.0,
        total_distance_m=5000.0,
        avg_heart_rate=130,
        max_heart_rate=155,
        heart_rate_samples=hrs,
    )


@pytest.mark.asyncio
async def test_polar_db_failure_skips_commit_batch(db_session):
    """If DB persistence fails, Polar commit_batch MUST NOT be called and failed audit log is saved cleanly."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    uid = user.id

    acct = IntegrationAccount(
        user_id=uid,
        provider="polar",
        account_id="polar-u1",
        encrypted_access_token=encrypt_token("valid_polar_tok"),
        is_active=True,
    )
    db_session.add(acct)
    await db_session.commit()

    fake_adapter = MagicMock()
    fake_adapter.fetch_workouts_batch = AsyncMock(
        return_value=SyncBatchResult(
            workouts=[_make_workout("tx-fail-1")],
            next_cursor={"user_id": "polar-u1"},
            has_more=False,
            pending_commit_token={"tx_url": "https://polar.example/tx", "transaction_id": 999},
        )
    )
    fake_adapter.commit_batch = AsyncMock()

    with patch("src.services.sync_service.ingest_workout", side_effect=RuntimeError("DB disk full")):
        audit = await run_sync_for_account(db_session, acct, adapter_override=fake_adapter)

    fake_adapter.commit_batch.assert_not_awaited()
    assert audit.status == "failed"
    assert "DB disk full" in (audit.error_message or "")

    logs = (await db_session.execute(select(SyncAuditLog).where(SyncAuditLog.user_id == uid))).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == "failed"


@pytest.mark.asyncio
async def test_polar_db_success_calls_commit_batch_after_commit(db_session):
    """Polar commit_batch is invoked only after DB commit succeeds."""
    user = User()
    db_session.add(user)
    await db_session.flush()

    acct = IntegrationAccount(
        user_id=user.id,
        provider="polar",
        account_id="polar-u2",
        encrypted_access_token=encrypt_token("valid_polar_tok"),
        is_active=True,
    )
    db_session.add(acct)
    await db_session.commit()

    token = {"tx_url": "https://polar.example/tx", "transaction_id": 1234}
    fake_adapter = MagicMock()
    fake_adapter.fetch_workouts_batch = AsyncMock(
        return_value=SyncBatchResult(
            workouts=[_make_workout("tx-ok-1")],
            next_cursor={"user_id": "polar-u2"},
            has_more=False,
            pending_commit_token=token,
        )
    )
    fake_adapter.commit_batch = AsyncMock()

    audit = await run_sync_for_account(db_session, acct, adapter_override=fake_adapter)
    assert audit.status == "success"
    assert audit.items_imported == 1
    fake_adapter.commit_batch.assert_awaited_once_with("valid_polar_tok", token)


@pytest.mark.asyncio
async def test_concept2_multi_page_pagination_and_watermark(db_session):
    """Sync loops through all 3 pages and clears cursor / advances watermark only after final page succeeds."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    uid = user.id

    acct = IntegrationAccount(
        user_id=uid,
        provider="concept2",
        account_id="c2-u1",
        encrypted_access_token=encrypt_token("c2_tok"),
        is_active=True,
    )
    db_session.add(acct)
    await db_session.commit()

    pages = [
        SyncBatchResult(workouts=[_make_workout("p1", "concept2")], next_cursor={"page": 2}, has_more=True),
        SyncBatchResult(workouts=[_make_workout("p2", "concept2")], next_cursor={"page": 3}, has_more=True),
        SyncBatchResult(workouts=[_make_workout("p3", "concept2")], next_cursor=None, has_more=False),
    ]
    fake_adapter = MagicMock()
    fake_adapter.fetch_workouts_batch = AsyncMock(side_effect=pages)
    fake_adapter.commit_batch = AsyncMock()

    audit = await run_sync_for_account(db_session, acct, adapter_override=fake_adapter)
    assert audit.status == "success"
    assert audit.items_imported == 3
    assert audit.diagnostic_metadata == {"pages_fetched": 3}
    assert fake_adapter.fetch_workouts_batch.await_count == 3

    workouts = (await db_session.execute(select(WorkoutSession).where(WorkoutSession.user_id == uid))).scalars().all()
    assert {w.external_id for w in workouts} == {"p1", "p2", "p3"}
    assert acct.sync_cursor is None
    assert acct.last_sync_at is not None


@pytest.mark.asyncio
async def test_sync_refreshes_token_on_401_and_retries(db_session):
    """401 HTTPStatusError triggers OAuth token refresh and retries once."""
    user = User()
    db_session.add(user)
    await db_session.flush()

    acct = IntegrationAccount(
        user_id=user.id,
        provider="concept2",
        account_id="c2-u401",
        encrypted_access_token=encrypt_token("expired_tok"),
        encrypted_refresh_token=encrypt_token("valid_refresh"),
        is_active=True,
    )
    db_session.add(acct)
    await db_session.commit()

    req = httpx.Request("GET", "https://log.concept2.com/api/users/me/results")
    err_401 = httpx.HTTPStatusError("Unauthorized", request=req, response=httpx.Response(401, request=req))

    fake_adapter = MagicMock()
    fake_adapter.fetch_workouts_batch = AsyncMock(
        side_effect=[
            err_401,
            SyncBatchResult(workouts=[_make_workout("recovered-1", "concept2")], next_cursor=None, has_more=False),
        ]
    )
    fake_adapter.commit_batch = AsyncMock()
    fake_adapter.refresh_access_token = AsyncMock(
        return_value={"access_token": "fresh_tok", "refresh_token": "fresh_ref"}
    )

    audit = await run_sync_for_account(db_session, acct, adapter_override=fake_adapter)

    assert audit.status == "success"
    assert audit.items_imported == 1
    fake_adapter.refresh_access_token.assert_awaited_once_with("valid_refresh")
    assert fake_adapter.fetch_workouts_batch.await_count == 2


@pytest.mark.asyncio
async def test_transient_429_and_503_retry_backoff():
    """request_with_retry honors Retry-After on 429 and retries transient 503."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        if attempts == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await request_with_retry(client, "GET", "https://api.example.com/data", max_attempts=3, base_delay_sec=0.01)
    assert resp.status_code == 200
    assert attempts == 3


@pytest.mark.asyncio
async def test_soft_sync_preserves_existing_hr_zones(db_session):
    """Re-ingesting metadata without HR samples MUST NOT wipe existing zone1..zone5."""
    user = User()
    db_session.add(user)
    await db_session.flush()

    profile = UserHeartRateProfile(
        user_id=user.id,
        max_hr=185,
        resting_hr=50,
        zone1_min=90,
        zone1_max=115,
        zone2_min=116,
        zone2_max=135,
        zone3_min=136,
        zone3_max=150,
        zone4_min=151,
        zone4_max=165,
        zone5_min=166,
        zone5_max=185,
    )
    db_session.add(profile)
    await db_session.flush()

    w1, created = await ingest_workout(db_session, user.id, _make_workout("z-keep-1", with_hr=True), profile)
    assert created is True
    orig_zones = (
        w1.zone1_duration_sec,
        w1.zone2_duration_sec,
        w1.zone3_duration_sec,
        w1.zone4_duration_sec,
        w1.zone5_duration_sec,
    )
    assert sum(orig_zones) > 0

    meta_only = _make_workout("z-keep-1", with_hr=False)
    meta_only.total_calories = 420
    w2, created2 = await ingest_workout(db_session, user.id, meta_only, profile)
    assert created2 is False
    assert w2.total_calories == 420
    assert (
        w2.zone1_duration_sec,
        w2.zone2_duration_sec,
        w2.zone3_duration_sec,
        w2.zone4_duration_sec,
        w2.zone5_duration_sec,
    ) == orig_zones


@pytest.mark.asyncio
async def test_scheduler_multi_account_isolation(db_session):
    """If one account fails during scheduled sync, subsequent accounts still sync in their own isolated sessions."""
    user = User()
    db_session.add(user)
    await db_session.flush()

    a1 = IntegrationAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="polar",
        account_id="p-iso-1",
        encrypted_access_token=encrypt_token("tok1"),
        is_active=True,
    )
    a2 = IntegrationAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="concept2",
        account_id="c2-iso-2",
        encrypted_access_token=encrypt_token("tok2"),
        is_active=True,
    )
    db_session.add_all([a1, a2])
    await db_session.commit()

    synced_providers: list[str] = []

    async def fake_run_sync(session, acc, trigger_type="manual"):
        synced_providers.append(acc.provider)
        if acc.provider == "polar":
            raise RuntimeError("Polar exploded")
        return MagicMock(status="success")

    test_factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)

    with (
        patch("src.core.scheduler.async_session_factory", test_factory),
        patch("src.core.scheduler.run_sync_for_account", side_effect=fake_run_sync),
    ):
        await _run_isolated_sync_pass()

    assert set(synced_providers) == {"polar", "concept2"}


@pytest.mark.asyncio
async def test_recover_orphaned_sync_logs(db_session):
    """Startup recovery marks orphaned 'running' SyncAuditLogs as failed."""
    user = User()
    db_session.add(user)
    await db_session.flush()

    orphan = SyncAuditLog(
        user_id=user.id,
        provider="polar",
        trigger_type="hourly_schedule",
        status="running",
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    ok_log = SyncAuditLog(
        user_id=user.id,
        provider="concept2",
        trigger_type="manual",
        status="success",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([orphan, ok_log])
    await db_session.commit()

    recovered = await recover_orphaned_sync_logs(db_session)
    await db_session.commit()
    assert recovered == 1

    await db_session.refresh(orphan)
    await db_session.refresh(ok_log)
    assert orphan.status == "failed"
    assert orphan.completed_at is not None
    assert "Interrupted" in (orphan.error_message or "")
    assert ok_log.status == "success"
