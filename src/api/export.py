"""API endpoint for downloading the complete athlete training history ZIP archive."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_or_create_default_user
from src.services.export_service import ExportService

router = APIRouter(prefix="/api/v1/export", tags=["Export"])


@router.get("")
async def download_training_history_zip(
    include_demo: bool = Query(default=False, description="Include synthetic is_demo=True workouts"),
    db: AsyncSession = Depends(get_db),
):
    """Download a lossless ZIP archive containing backup.json, workouts.csv, and strength_sets.csv."""
    user = await get_or_create_default_user(db)
    zip_bytes = await ExportService.build_export_zip(db, user, include_demo=include_demo)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="coach3-backup-{stamp}.zip"',
            "Cache-Control": "no-store",
        },
    )
