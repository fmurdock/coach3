"""Service orchestrating background synchronization, pagination, and audit logging."""

from datetime import datetime, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.base import BaseIngestionAdapter, NormalizedWorkout
from src.adapters.concept2 import Concept2Adapter
from src.adapters.polar import PolarAdapter
from src.core.security import decrypt_token
from src.models.integration import IntegrationAccount, SyncAuditLog
from src.models.user import UserHeartRateProfile
from src.services.ingestion import ingest_workout


def get_adapter_for_provider(provider: str) -> BaseIngestionAdapter:
    if provider == "polar":
        return PolarAdapter()
    elif provider == "concept2":
        return Concept2Adapter()
    raise ValueError(f"Unsupported provider: {provider}")


async def run_sync_for_account(
    db: AsyncSession,
    account: IntegrationAccount,
    trigger_type: str = "manual",
    mock_batch: list[NormalizedWorkout] | None = None,
) -> SyncAuditLog:
    """Execute a sync job for an integration account, recording audit history."""
    now = datetime.now(timezone.utc)
    audit_log = SyncAuditLog(
        id=uuid.uuid4(),
        user_id=account.user_id,
        provider=account.provider,
        trigger_type=trigger_type,
        started_at=now,
        status="running",
        items_imported=0,
        items_updated=0,
    )
    db.add(audit_log)
    await db.flush()

    try:
        # Load user HR profile for local zone math (auto-create default if missing)
        q_prof = select(UserHeartRateProfile).where(UserHeartRateProfile.user_id == account.user_id)
        res_prof = await db.execute(q_prof)
        hr_profile = res_prof.scalar_one_or_none()
        if not hr_profile:
            hr_profile = UserHeartRateProfile(
                id=uuid.uuid4(),
                user_id=account.user_id,
                resting_hr=50,
                max_hr=190,
                zone1_min=95,
                zone1_max=114,
                zone2_min=114,
                zone2_max=133,
                zone3_min=133,
                zone3_max=152,
                zone4_min=152,
                zone4_max=171,
                zone5_min=171,
                zone5_max=190,
            )
            db.add(hr_profile)
            await db.flush()

        adapter = get_adapter_for_provider(account.provider)
        token = decrypt_token(account.encrypted_access_token)

        imported_count = 0
        updated_count = 0

        # If a mock batch is provided (for testing or direct dispatch), use it;
        # otherwise fetch from adapter API
        if mock_batch is not None:
            workouts_to_process = mock_batch
        else:
            cursor = dict(account.sync_cursor or {})
            if account.provider == "polar" and account.account_id and "user_id" not in cursor:
                cursor["user_id"] = account.account_id

            batch_result = await adapter.fetch_workouts_batch(
                access_token=token,
                cursor=cursor,
                since=account.last_sync_at,
            )
            workouts_to_process = batch_result.workouts
            if batch_result.next_cursor:
                account.sync_cursor = batch_result.next_cursor

        for w in workouts_to_process:
            _, is_new = await ingest_workout(
                session=db,
                user_id=account.user_id,
                normalized=w,
                hr_profile=hr_profile,
            )
            if is_new:
                imported_count += 1
            else:
                updated_count += 1

        account.last_sync_at = datetime.now(timezone.utc)
        audit_log.status = "success"
        audit_log.items_imported = imported_count
        audit_log.items_updated = updated_count
        audit_log.completed_at = datetime.now(timezone.utc)

    except Exception as exc:
        audit_log.status = "failed"
        audit_log.error_message = str(exc)
        audit_log.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return audit_log
