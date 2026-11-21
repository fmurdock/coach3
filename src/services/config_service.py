"""Service for managing external integration developer credentials with database encryption and .env fallback."""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import decrypt_token, encrypt_token
from src.models.integration import IntegrationAccount, IntegrationClientConfig
from src.schemas.config import ProviderConfigSummary


class ConfigService:
    @staticmethod
    def mask_client_id(client_id: str | None) -> str | None:
        """Masks client ID for safe UI display while confirming its existence."""
        if not client_id:
            return None
        if len(client_id) <= 6:
            return "••••••"
        return f"{client_id[:3]}••••{client_id[-3:]}"

    @classmethod
    async def get_provider_credentials(
        cls, db: AsyncSession, provider: str
    ) -> tuple[str | None, str | None, str | None, str]:
        """Resolves OAuth client ID, client secret, and redirect URI with DB-first precedence.
        
        Returns:
            (client_id, client_secret, redirect_uri, source) where source is 'database', 'env', or 'none'.
        """
        # 1. Check database first
        q = select(IntegrationClientConfig).where(
            IntegrationClientConfig.provider == provider,
            IntegrationClientConfig.is_active == True,
        )
        res = await db.execute(q)
        db_config = res.scalars().first()

        if db_config:
            client_id = decrypt_token(db_config.encrypted_client_id)
            client_secret = decrypt_token(db_config.encrypted_client_secret)
            redirect_uri = db_config.redirect_uri or (
                settings.POLAR_REDIRECT_URI if provider == "polar" else settings.CONCEPT2_REDIRECT_URI
            )
            return client_id, client_secret, redirect_uri, "database"

        # 2. Fall back to environment settings
        if provider == "polar":
            if settings.POLAR_CLIENT_ID and settings.POLAR_CLIENT_SECRET:
                return (
                    settings.POLAR_CLIENT_ID,
                    settings.POLAR_CLIENT_SECRET,
                    settings.POLAR_REDIRECT_URI,
                    "env",
                )
        elif provider == "concept2":
            if settings.CONCEPT2_CLIENT_ID and settings.CONCEPT2_CLIENT_SECRET:
                return (
                    settings.CONCEPT2_CLIENT_ID,
                    settings.CONCEPT2_CLIENT_SECRET,
                    settings.CONCEPT2_REDIRECT_URI,
                    "env",
                )

        # 3. Not configured
        default_redirect = settings.POLAR_REDIRECT_URI if provider == "polar" else settings.CONCEPT2_REDIRECT_URI
        return None, None, default_redirect, "none"

    @classmethod
    async def save_provider_credentials(
        cls,
        db: AsyncSession,
        provider: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str | None = None,
    ) -> IntegrationClientConfig:
        """Encrypts and upserts provider client credentials into PostgreSQL."""
        if provider not in ("polar", "concept2"):
            raise ValueError(f"Unsupported provider: {provider}")

        q = select(IntegrationClientConfig).where(IntegrationClientConfig.provider == provider)
        res = await db.execute(q)
        existing = res.scalars().first()

        enc_id = encrypt_token(client_id.strip())
        enc_secret = encrypt_token(client_secret.strip())

        if existing:
            existing.encrypted_client_id = enc_id
            existing.encrypted_client_secret = enc_secret
            if redirect_uri:
                existing.redirect_uri = redirect_uri.strip()
            existing.is_active = True
            await db.commit()
            await db.refresh(existing)
            return existing

        new_config = IntegrationClientConfig(
            id=uuid.uuid4(),
            provider=provider,
            encrypted_client_id=enc_id,
            encrypted_client_secret=enc_secret,
            redirect_uri=redirect_uri.strip() if redirect_uri else None,
            is_active=True,
        )
        db.add(new_config)
        await db.commit()
        await db.refresh(new_config)
        return new_config

    @classmethod
    async def get_all_provider_summaries(
        cls, db: AsyncSession, user_id: uuid.UUID
    ) -> list[ProviderConfigSummary]:
        """Returns configuration and connection status for both Polar and Concept2."""
        summaries = []
        for prov in ("polar", "concept2"):
            cid, _, _, source = await cls.get_provider_credentials(db, prov)
            is_configured = bool(cid)

            # Check if user has an active connection
            q_acc = select(IntegrationAccount).where(
                IntegrationAccount.user_id == user_id,
                IntegrationAccount.provider == prov,
                IntegrationAccount.is_active == True,
            )
            res_acc = await db.execute(q_acc)
            acc = res_acc.scalars().first()

            summaries.append(
                ProviderConfigSummary(
                    provider=prov,
                    is_configured=is_configured,
                    is_connected=acc is not None,
                    masked_client_id=cls.mask_client_id(cid),
                    source=source,  # type: ignore[arg-type]
                    account_id=acc.account_id if acc else None,
                    last_sync_at=acc.last_sync_at if acc else None,
                )
            )
        return summaries
