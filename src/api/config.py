"""API endpoints for integration credentials configuration and overview."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_or_create_default_user
from src.schemas.config import ProviderConfigSummary, SaveProviderCredentialsRequest
from src.services.config_service import ConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])


@router.get("/integrations", response_model=list[ProviderConfigSummary])
async def get_all_integration_configs(db: AsyncSession = Depends(get_db)):
    """Returns configuration summaries for Polar and Concept2."""
    user = await get_or_create_default_user(db)
    return await ConfigService.get_all_provider_summaries(db, user.id)


@router.post("/integrations/{provider}", response_model=ProviderConfigSummary)
async def save_integration_credentials(
    provider: str,
    payload: SaveProviderCredentialsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Encrypts and persists OAuth developer credentials in the database."""
    if provider not in ("polar", "concept2"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    try:
        await ConfigService.save_provider_credentials(
            db,
            provider=provider,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            redirect_uri=payload.redirect_uri,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error saving %s integration credentials", provider)
        raise HTTPException(status_code=500, detail="Failed to save provider credentials.") from exc

    user = await get_or_create_default_user(db)
    summaries = await ConfigService.get_all_provider_summaries(db, user.id)
    summary = next((s for s in summaries if s.provider == provider), None)
    if not summary:
        raise HTTPException(status_code=500, detail="Failed to retrieve saved config.")
    return summary
