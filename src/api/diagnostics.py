"""System health, schema revision, scheduler, and sync diagnostics endpoint."""

from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_or_create_default_user
from src.core.scheduler import get_next_sync_time, scheduler
from src.models.integration import SyncAuditLog
from src.schemas.config import ProviderConfigSummary
from src.services.config_service import ConfigService

router = APIRouter(prefix="/api/v1/system", tags=["System Diagnostics"])


class RecentSyncLogItem(BaseModel):
    id: str
    provider: str
    trigger_type: str
    status: str
    items_imported: int
    items_updated: int
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class SystemDiagnosticsResponse(BaseModel):
    database_ok: bool
    alembic_revision: str | None = None
    scheduler_running: bool
    next_scheduled_sync_at: datetime | None = None
    has_recent_sync_failures: bool = False
    providers: list[ProviderConfigSummary] = Field(default_factory=list)
    recent_sync_logs: list[RecentSyncLogItem] = Field(default_factory=list)


@router.get("/diagnostics", response_model=SystemDiagnosticsResponse)
async def get_system_diagnostics(db: AsyncSession = Depends(get_db)):
    """Return operational health, Alembic revision, scheduler schedule, provider decryption state, and latest sync logs."""
    db_ok = True
    alembic_rev: str | None = None
    try:
        await db.execute(text("SELECT 1"))
        try:
            rev_res = await db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            alembic_rev = rev_res.scalar()
        except Exception:
            alembic_rev = None
    except Exception:
        db_ok = False

    user = await get_or_create_default_user(db)
    providers = await ConfigService.get_all_provider_summaries(db, user.id)

    logs_res = await db.execute(
        select(SyncAuditLog)
        .where(SyncAuditLog.user_id == user.id)
        .order_by(desc(SyncAuditLog.started_at))
        .limit(10)
    )
    logs = logs_res.scalars().all()

    recent_items = [
        RecentSyncLogItem(
            id=str(log.id),
            provider=log.provider,
            trigger_type=log.trigger_type,
            status=log.status,
            items_imported=log.items_imported,
            items_updated=log.items_updated,
            started_at=log.started_at,
            completed_at=log.completed_at,
            error_message=log.error_message,
        )
        for log in logs
    ]

    has_failures = any(log.status == "failed" for log in logs) or any(p.decryption_error for p in providers)

    return SystemDiagnosticsResponse(
        database_ok=db_ok,
        alembic_revision=alembic_rev,
        scheduler_running=bool(scheduler.running),
        next_scheduled_sync_at=get_next_sync_time(),
        has_recent_sync_failures=has_failures,
        providers=providers,
        recent_sync_logs=recent_items,
    )
