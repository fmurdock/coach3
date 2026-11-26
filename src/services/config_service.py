"""Service for managing external integration developer credentials with database encryption and .env fallback."""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import decrypt_token_safe, encrypt_token
from src.models.integration import IntegrationAccount, IntegrationClientConfig
from src.schemas.config import ProviderConfigSummary

MASK_BULLET = "\u2022"


class ConfigService:
    @staticmethod
    def mask_client_id(client_id: str | None) -> str | None:
        """Masks client ID for safe UI display while confirming its existence."""
        if not client_id:
            return None
        if len(client_id) <= 6:
            return "••••••"
        return f"{client_id[:3]}••••{client_id[-3:]}"

    @staticmethod
    def _reject_masked_input(value: str | None, field_name: str) -> None:
        if value and MASK_BULLET in value:
            raise ValueError(
                f"Invalid {field_name}: masked placeholder characters ('•') cannot be saved as credentials."
            )

    @classmethod
    async def get_provider_credentials(
        cls, db: AsyncSession, provider: str
    ) -> tuple[str | None, str | None, str | None, str]:
        """Resolves OAuth client ID, client secret, and redirect URI with DB-first precedence.

        Returns:
            (client_id, client_secret, redirect_uri, source) where source is
            'database', 'env', 'decryption_error', or 'none'.
        """
        default_redirect = (
            settings.POLAR_REDIRECT_URI if provider == "polar" else settings.CONCEPT2_REDIRECT_URI
        )

        # 1. Check database first
        q = select(IntegrationClientConfig).where(
            IntegrationClientConfig.provider == provider,
            IntegrationClientConfig.is_active.is_(True),
        )
        res = await db.execute(q)
        db_config = res.scalars().first()

        if db_config:
            redirect_uri = db_config.redirect_uri or default_redirect
            client_id, id_err = decrypt_token_safe(
                db_config.encrypted_client_id, context=f"{provider}_client_id"
            )
            client_secret, sec_err = decrypt_token_safe(
                db_config.encrypted_client_secret, context=f"{provider}_client_secret"
            )
            if id_err or sec_err or not client_id or not client_secret:
                return None, None, redirect_uri, "decryption_error"
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
        return None, None, default_redirect, "none"

    @classmethod
    async def save_provider_credentials(
        cls,
        db: AsyncSession,
        provider: str,
        client_id: str | None,
        client_secret: str,
        redirect_uri: str | None = None,
    ) -> IntegrationClientConfig:
        """Encrypts and upserts provider client credentials into the database (flushes; caller commits)."""
        if provider not in ("polar", "concept2"):
            raise ValueError(f"Unsupported provider: {provider}")

        cls._reject_masked_input(client_id, "client_id")
        cls._reject_masked_input(client_secret, "client_secret")

        cleaned_secret = client_secret.strip()
        if not cleaned_secret:
            raise ValueError("Client Secret cannot be blank.")

        cleaned_id = client_id.strip() if client_id else ""

        q = select(IntegrationClientConfig).where(IntegrationClientConfig.provider == provider)
        res = await db.execute(q)
        existing = res.scalars().first()

        enc_secret = encrypt_token(cleaned_secret)

        if existing:
            if cleaned_id:
                existing.encrypted_client_id = encrypt_token(cleaned_id)
            else:
                # Secret-only rotation requires an existing decryptable Client ID
                existing_id, id_err = decrypt_token_safe(
                    existing.encrypted_client_id, context=f"{provider}_client_id"
                )
                if id_err or not existing_id:
                    raise ValueError(
                        "Client ID is required because the stored Client ID cannot be decrypted."
                    )
            existing.encrypted_client_secret = enc_secret
            if redirect_uri is not None and redirect_uri.strip():
                existing.redirect_uri = redirect_uri.strip()
            existing.is_active = True
            await db.flush()
            return existing

        if not cleaned_id:
            raise ValueError("Client ID is required when configuring a provider for the first time.")

        new_config = IntegrationClientConfig(
            id=uuid.uuid4(),
            provider=provider,
            encrypted_client_id=encrypt_token(cleaned_id),
            encrypted_client_secret=enc_secret,
            redirect_uri=redirect_uri.strip() if redirect_uri and redirect_uri.strip() else None,
            is_active=True,
        )
        db.add(new_config)
        await db.flush()
        return new_config

    @classmethod
    async def get_all_provider_summaries(
        cls, db: AsyncSession, user_id: uuid.UUID
    ) -> list[ProviderConfigSummary]:
        """Returns configuration and connection status for both Polar and Concept2."""
        summaries = []
        for prov in ("polar", "concept2"):
            cid, _, _, source = await cls.get_provider_credentials(db, prov)
            decryption_error = source == "decryption_error"
            is_configured = bool(cid) and not decryption_error

            q_acc = select(IntegrationAccount).where(
                IntegrationAccount.user_id == user_id,
                IntegrationAccount.provider == prov,
                IntegrationAccount.is_active.is_(True),
            )
            res_acc = await db.execute(q_acc)
            acc = res_acc.scalars().first()

            # Also detect corrupted OAuth access token on connected account
            if acc and not decryption_error:
                _, tok_err = decrypt_token_safe(
                    acc.encrypted_access_token, context=f"{prov}_access_token"
                )
                if tok_err:
                    decryption_error = True

            summaries.append(
                ProviderConfigSummary(
                    provider=prov,
                    is_configured=is_configured,
                    is_connected=acc is not None,
                    masked_client_id=cls.mask_client_id(cid),
                    source=source,  # type: ignore[arg-type]
                    decryption_error=decryption_error,
                    account_id=acc.account_id if acc else None,
                    last_sync_at=acc.last_sync_at if acc else None,
                )
            )
        return summaries
