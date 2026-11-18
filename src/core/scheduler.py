"""APScheduler background service for 60-minute recurring synchronization."""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from src.core.config import settings
from src.core.database import async_session_factory
from src.models.integration import IntegrationAccount
from src.services.sync_service import run_sync_for_account

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_sync_job():
    """Periodic job executed every 60 minutes to poll all active integrations."""
    logger.info("Executing scheduled recurring sync job...")
    async with async_session_factory() as db:
        try:
            query = select(IntegrationAccount).where(IntegrationAccount.is_active.is_(True))
            result = await db.execute(query)
            accounts = result.scalars().all()

            for account in accounts:
                logger.info(f"Syncing account {account.id} ({account.provider})")
                await run_sync_for_account(db, account, trigger_type="hourly_schedule")

        except Exception as e:
            logger.error(f"Error during scheduled sync: {e}", exc_info=True)


def start_scheduler():
    """Start the background scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            scheduled_sync_job,
            "interval",
            minutes=settings.SYNC_INTERVAL_MINUTES,
            id="recurring_sync_job",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"Scheduler started with {settings.SYNC_INTERVAL_MINUTES} min interval.")


def stop_scheduler():
    """Shutdown the background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
