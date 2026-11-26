"""Unit tests for ConfigService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.services.config_service import ConfigService


@pytest.mark.asyncio
async def test_mask_client_id():
    assert ConfigService.mask_client_id(None) is None
    assert ConfigService.mask_client_id("") is None
    assert ConfigService.mask_client_id("12345") == "••••••"
    assert ConfigService.mask_client_id("polar_client_99") == "pol••••_99"


@pytest.mark.asyncio
async def test_save_and_get_provider_credentials(db_session: AsyncSession):
    # Initially, if .env has no polar credentials, returns none
    orig_id = settings.POLAR_CLIENT_ID
    orig_secret = settings.POLAR_CLIENT_SECRET
    try:
        settings.POLAR_CLIENT_ID = ""
        settings.POLAR_CLIENT_SECRET = ""

        cid, csec, redir, src = await ConfigService.get_provider_credentials(db_session, "polar")
        assert cid is None
        assert csec is None
        assert src == "none"

        # Save credentials in DB
        await ConfigService.save_provider_credentials(
            db_session,
            provider="polar",
            client_id="my-polar-client-id",
            client_secret="my-polar-secret",
            redirect_uri="http://localhost:8000/callback",
        )

        # Now resolves from DB
        cid, csec, redir, src = await ConfigService.get_provider_credentials(db_session, "polar")
        assert cid == "my-polar-client-id"
        assert csec == "my-polar-secret"
        assert redir == "http://localhost:8000/callback"
        assert src == "database"

        # Update existing credentials
        await ConfigService.save_provider_credentials(
            db_session,
            provider="polar",
            client_id="my-updated-client-id",
            client_secret="my-updated-secret",
        )

        cid, csec, redir, src = await ConfigService.get_provider_credentials(db_session, "polar")
        assert cid == "my-updated-client-id"
        assert csec == "my-updated-secret"
        assert src == "database"
    finally:
        settings.POLAR_CLIENT_ID = orig_id
        settings.POLAR_CLIENT_SECRET = orig_secret


@pytest.mark.asyncio
async def test_provider_summaries(db_session: AsyncSession, sample_user):
    user, _ = sample_user
    summaries = await ConfigService.get_all_provider_summaries(db_session, user.id)
    assert len(summaries) == 2
    providers = {s.provider for s in summaries}
    assert providers == {"polar", "concept2"}


@pytest.mark.asyncio
async def test_reject_masked_bullets_and_support_secret_only_rotation(db_session: AsyncSession):
    await ConfigService.save_provider_credentials(
        db_session,
        provider="polar",
        client_id="real-polar-client-id-123",
        client_secret="initial-secret",
    )

    # Reject bullet characters in client_id or client_secret
    with pytest.raises(ValueError, match="masked placeholder"):
        await ConfigService.save_provider_credentials(
            db_session,
            provider="polar",
            client_id="rea••••123",
            client_secret="new-secret",
        )

    with pytest.raises(ValueError, match="masked placeholder"):
        await ConfigService.save_provider_credentials(
            db_session,
            provider="polar",
            client_id=None,
            client_secret="••••••",
        )

    # Secret-only rotation preserves existing Client ID cleanly
    await ConfigService.save_provider_credentials(
        db_session,
        provider="polar",
        client_id=None,
        client_secret="rotated-secret-456",
    )
    cid, csec, _, src = await ConfigService.get_provider_credentials(db_session, "polar")
    assert cid == "real-polar-client-id-123"
    assert csec == "rotated-secret-456"
    assert src == "database"


@pytest.mark.asyncio
async def test_decryption_error_degrades_gracefully(db_session: AsyncSession, sample_user):
    from src.models.integration import IntegrationClientConfig

    user, _ = sample_user
    bad_cfg = IntegrationClientConfig(
        provider="concept2",
        encrypted_client_id="not-a-valid-fernet-token",
        encrypted_client_secret="also-invalid",
        is_active=True,
    )
    db_session.add(bad_cfg)
    await db_session.flush()

    cid, csec, _, src = await ConfigService.get_provider_credentials(db_session, "concept2")
    assert cid is None
    assert csec is None
    assert src == "decryption_error"

    summaries = await ConfigService.get_all_provider_summaries(db_session, user.id)
    c2 = next(s for s in summaries if s.provider == "concept2")
    assert c2.decryption_error is True
    assert c2.is_configured is False
    assert c2.source == "decryption_error"

