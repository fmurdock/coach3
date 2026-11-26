"""Service orchestrating background synchronization, full pagination, deferred commits, and audit logging."""

from datetime import datetime, timezone
import logging
import uuid
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.base import BaseIngestionAdapter, NormalizedWorkout, SyncBatchResult
from src.adapters.concept2 import Concept2Adapter
from src.adapters.polar import PolarAdapter
from src.core.config import settings
from src.core.deps import get_or_create_default_hr_profile
from src.core.logging import redact_secrets
from src.core.security import decrypt_token_safe, encrypt_token
from src.models.integration import IntegrationAccount, SyncAuditLog
from src.services.config_service import ConfigService
from src.services.ingestion import ingest_workout

logger = logging.getLogger(__name__)


def get_adapter_for_provider(provider: str) -> BaseIngestionAdapter:
    if provider == "polar":
        return PolarAdapter()
    elif provider == "concept2":
        return Concept2Adapter()
    raise ValueError(f"Unsupported provider: {provider}")


async def _fetch_page_with_401_refresh(
    db: AsyncSession,
    adapter: BaseIngestionAdapter,
    account: IntegrationAccount,
    access_token: str,
    cursor: dict | None,
    since: datetime | None,
) -> tuple[SyncBatchResult, str]:
    """Fetch a single batch page, refreshing OAuth token strictly on HTTP 401 Unauthorized."""
    try:
        batch = await adapter.fetch_workouts_batch(
            access_token=access_token,
            cursor=cursor,
            since=since,
        )
        return batch, access_token
    except httpx.HTTPStatusError as http_err:
        if http_err.response.status_code != 401 or not account.encrypted_refresh_token:
            raise
        refresh_tok, ref_err = decrypt_token_safe(
            account.encrypted_refresh_token,
            context=f"{account.provider}_refresh_token",
        )
        if ref_err or not refresh_tok:
            raise ValueError(f"Stored {account.provider} refresh token could not be decrypted.") from http_err

        new_tokens = await adapter.refresh_access_token(refresh_tok)
        new_access = new_tokens.get("access_token")
        if not new_access:
            raise http_err

        account.encrypted_access_token = encrypt_token(new_access)
        if new_tokens.get("refresh_token"):
            account.encrypted_refresh_token = encrypt_token(new_tokens["refresh_token"])
        await db.flush()

        batch = await adapter.fetch_workouts_batch(
            access_token=new_access,
            cursor=cursor,
            since=since,
        )
        return batch, new_access


async def run_sync_for_account(
    db: AsyncSession,
    account: IntegrationAccount,
    trigger_type: str = "manual",
    mock_batch: list[NormalizedWorkout] | None = None,
    adapter_override: BaseIngestionAdapter | None = None,
) -> SyncAuditLog:
    """Execute a full sync job for an integration account with safe rollback and deferred Polar commit."""
    started_at = datetime.now(timezone.utc)
    account_id = account.id
    user_id = account.user_id
    provider = account.provider
    audit_log_id = uuid.uuid4()

    audit_log = SyncAuditLog(
        id=audit_log_id,
        user_id=user_id,
        provider=provider,
        trigger_type=trigger_type,
        started_at=started_at,
        status="running",
        items_imported=0,
        items_updated=0,
    )
    db.add(audit_log)
    await db.commit()

    imported_count = 0
    updated_count = 0
    pages_fetched = 0

    try:
        hr_profile = await get_or_create_default_hr_profile(db, user_id)

        if adapter_override is not None:
            adapter = adapter_override
        else:
            cid, csec, redir, source = await ConfigService.get_provider_credentials(db, provider)
            if source == "decryption_error":
                raise ValueError(
                    f"Stored {provider} client credentials could not be decrypted with ENCRYPTION_KEY."
                )
            if provider == "polar":
                adapter = PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
            elif provider == "concept2":
                adapter = Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)
            else:
                adapter = get_adapter_for_provider(provider)

        token, token_err = decrypt_token_safe(
            account.encrypted_access_token,
            context=f"{provider}_access_token",
        )
        if token_err or not token:
            raise ValueError(
                f"Stored {provider} access token could not be decrypted. Please reconnect in Settings."
            )

        if mock_batch is not None:
            for w in mock_batch:
                _, is_new = await ingest_workout(
                    session=db,
                    user_id=user_id,
                    normalized=w,
                    hr_profile=hr_profile,
                )
                if is_new:
                    imported_count += 1
                else:
                    updated_count += 1
            account.last_sync_at = datetime.now(timezone.utc)
        else:
            cursor: dict | None = dict(account.sync_cursor) if account.sync_cursor else None
            if provider == "polar" and account.account_id:
                cursor = dict(cursor or {})
                cursor.setdefault("user_id", account.account_id)

            # Freeze incremental `since` watermark for the duration of this multi-page pass
            since_watermark = account.last_sync_at
            max_pages = settings.SYNC_PAGE_LIMIT
            completed_all_pages = False

            while pages_fetched < max_pages:
                batch_result, token = await _fetch_page_with_401_refresh(
                    db=db,
                    adapter=adapter,
                    account=account,
                    access_token=token,
                    cursor=cursor,
                    since=since_watermark,
                )
                pages_fetched += 1

                for w in batch_result.workouts:
                    _, is_new = await ingest_workout(
                        session=db,
                        user_id=user_id,
                        normalized=w,
                        hr_profile=hr_profile,
                    )
                    if is_new:
                        imported_count += 1
                    else:
                        updated_count += 1

                if batch_result.has_more and batch_result.next_cursor:
                    cursor = batch_result.next_cursor
                    account.sync_cursor = cursor
                else:
                    completed_all_pages = True
                    # Preserve Polar user_id cursor metadata, clear Concept2 pagination page
                    account.sync_cursor = {"user_id": account.account_id} if provider == "polar" else None

                # Durably commit this page to Postgres BEFORE acknowledging remote Polar transaction!
                await db.commit()

                if batch_result.pending_commit_token:
                    await adapter.commit_batch(token, batch_result.pending_commit_token)

                if completed_all_pages:
                    break

            if completed_all_pages:
                account.last_sync_at = datetime.now(timezone.utc)

        audit_log.status = "success"
        audit_log.items_imported = imported_count
        audit_log.items_updated = updated_count
        audit_log.completed_at = datetime.now(timezone.utc)
        audit_log.diagnostic_metadata = {"pages_fetched": pages_fetched}
        await db.commit()
        return audit_log

    except Exception as exc:
        # Cleanly roll back any partial/aborted writes before recording failed audit state
        await db.rollback()
        safe_msg = redact_secrets(str(exc))[:1000]
        logger.error("Sync failed for account %s (%s): %s", account_id, provider, safe_msg)

        failed_audit = await db.get(SyncAuditLog, audit_log_id)
        if failed_audit is None:
            failed_audit = SyncAuditLog(
                id=audit_log_id,
                user_id=user_id,
                provider=provider,
                trigger_type=trigger_type,
                started_at=started_at,
                items_imported=imported_count,
                items_updated=updated_count,
            )
            db.add(failed_audit)
        failed_audit.status = "failed"
        failed_audit.error_message = safe_msg
        failed_audit.items_imported = imported_count
        failed_audit.items_updated = updated_count
        failed_audit.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return failed_audit
