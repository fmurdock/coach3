"""Unit tests verifying AI provider configuration persistence and retrieval."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.coaching import LLMProviderConfig
from src.services.philosophy_service import PhilosophyService


@pytest.mark.asyncio
async def test_ai_provider_creation_and_active_flag(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    import uuid

    # Create active Gemini provider
    prov = LLMProviderConfig(
        id=uuid.uuid4(),
        user_id=user.id,
        provider_type="gemini",
        endpoint_url="https://generativelanguage.googleapis.com",
        model_name="gemini-2.5-flash",
        is_active=True,
    )
    db_session.add(prov)
    await db_session.commit()

    q = select(LLMProviderConfig).where(
        LLMProviderConfig.user_id == user.id,
        LLMProviderConfig.is_active == True,
    )
    res = await db_session.execute(q)
    active_prov = res.scalars().first()

    assert active_prov is not None
    assert active_prov.provider_type == "gemini"
    assert active_prov.model_name == "gemini-2.5-flash"
