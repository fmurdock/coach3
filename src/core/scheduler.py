"""APScheduler background service for recurring synchronization, orphan recovery, and pruning."""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import async_session_factory
from src.models.integration import IntegrationAccount, SyncAuditLog
from src.services.sync_service import run_sync_for_account

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
SCHEDULER_ADVISORY_LOCK_KEY = 307001
AUDIT_RETENTION_DAYS = 90
AUDIT_MIN_KEEP_PER_PROVIDER = 50

_active_sync_task: asyncio.Task[None] | None = None


async def recover_orphaned_sync_logs(db: AsyncSession) -> int:
    """Mark any orphaned 'running' sync audit logs left behind by a crash/restart as 'failed'."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(SyncAuditLog)
        .where(SyncAuditLog.status == "running")
        .values(
            status="failed",
            error_message="Interrupted by server restart",
            completed_at=now,
        )
    )
    res = await db.execute(stmt)
    return int(getattr(res, "rowcount", 0) or 0)


async def prune_old_sync_audit_logs(db: AsyncSession) -> int:
    """Prune SyncAuditLog rows older than 90 days while retaining at least 50 most recent per provider."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=AUDIT_RETENTION_DAYS)
    total_deleted = 0
    for provider in ("polar", "concept2"):
        keep_q = (
            select(SyncAuditLog.id)
            .where(SyncAuditLog.provider == provider)
            .order_by(SyncAuditLog.started_at.desc())
            .limit(AUDIT_MIN_KEEP_PER_PROVIDER)
        )
        keep_ids = list((await db.execute(keep_q)).scalars().all())
        del_stmt = delete(SyncAuditLog).where(
            SyncAuditLog.provider == provider,
            SyncAuditLog.started_at < cutoff,
        )
        if keep_ids:
            del_stmt = del_stmt.where(SyncAuditLog.id.not_in(keep_ids))
        res = await db.execute(del_stmt)
        total_deleted += int(getattr(res, "rowcount", 0) or 0)
    return total_deleted


async def _run_isolated_sync_pass() -> None:
    """Poll all active integration accounts using an isolated session per account."""
    lock_acquired = True
    lock_session: AsyncSession | None = None

    try:
        # Acquire PostgreSQL session advisory lock to prevent multi-worker duplicate syncs
        probe_session = async_session_factory()
        is_pg = probe_session.bind is not None and probe_session.bind.dialect.name == "postgresql"
        if is_pg:
            lock_session = probe_session
            res_lock = await lock_session.execute(
                text("SELECT pg_try_advisory_lock(:k)"),
                {"k": SCHEDULER_ADVISORY_LOCK_KEY},
            )
            lock_acquired = bool(res_lock.scalar())
            if not lock_acquired:
                logger.info("Scheduled sync skipped: another worker holds the sync advisory lock.")
                return
        else:
            await probe_session.close()

        async with async_session_factory() as list_db:
            q = select(IntegrationAccount.id).where(IntegrationAccount.is_active.is_(True))
            account_ids = list((await list_db.execute(q)).scalars().all())

        for acc_id in account_ids:
            async with async_session_factory() as acc_db:
                try:
                    acc = await acc_db.get(IntegrationAccount, acc_id)
                    if not acc or not acc.is_active:
                        continue
                    logger.info("Syncing account %s (%s)", acc.id, acc.provider)
                    await run_sync_for_account(acc_db, acc, trigger_type="hourly_schedule")
                except Exception as exc:
                    logger.error("Scheduled sync failed for account %s: %s", acc_id, exc, exc_info=True)
                    await acc_db.rollback()

        async with async_session_factory() as prune_db:
            pruned = await prune_old_sync_audit_logs(prune_db)
            await prune_db.commit()
            if pruned:
                logger.info("Pruned %d expired SyncAuditLog records", pruned)
    finally:
        if lock_session is not None:
            try:
                if lock_acquired:
                    await lock_session.execute(
                        text("SELECT pg_advisory_unlock(:k)"),
                        {"k": SCHEDULER_ADVISORY_LOCK_KEY},
                    )
            except Exception as exc:
                logger.debug("Ignoring advisory unlock error on shutdown: %s", exc)
            await lock_session.close()


async def scheduled_sync_job() -> None:
    """Periodic job executed on schedule to poll all active integrations."""
    global _active_sync_task
    logger.info("Executing scheduled recurring sync job...")
    _active_sync_task = asyncio.create_task(_run_isolated_sync_pass())
    try:
        await _active_sync_task
    finally:
        _active_sync_task = None


def get_next_sync_time() -> datetime | None:
    """Return the next scheduled run time if scheduler is active."""
    if not scheduler.running:
        return None
    job = scheduler.get_job("recurring_sync_job")
    return job.next_run_time if job else None


def start_scheduler() -> None:
    """Start the background scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            scheduled_sync_job,
            "interval",
            minutes=settings.SYNC_INTERVAL_MINUTES,
            id="recurring_sync_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        logger.info("Scheduler started with %d min interval.", settings.SYNC_INTERVAL_MINUTES)


async def stop_scheduler(drain_timeout_sec: float = 10.0) -> None:
    """Shutdown the background scheduler and gracefully drain any active sync task."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
    if _active_sync_task is not None and not _active_sync_task.done():
        logger.info("Draining in-flight background sync task (timeout=%.1fs)...", drain_timeout_sec)
        try:
            await asyncio.wait_for(asyncio.shield(_active_sync_task), timeout=drain_timeout_sec)
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for in-flight background sync to drain.")
        except Exception as exc:
            logger.debug("In-flight sync ended with error during shutdown drain: %s", exc)
