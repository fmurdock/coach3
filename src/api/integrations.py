"""API endpoints for managing integrations, OAuth flows (CSRF-protected), and triggering syncs."""

from datetime import datetime, timedelta, timezone
import logging
import secrets
import urllib.parse
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.concept2 import Concept2Adapter
from src.adapters.polar import PolarAdapter
from src.core.database import get_db
from src.core.deps import get_or_create_default_user
from src.core.logging import redact_secrets
from src.core.security import decrypt_token_safe, encrypt_token
from src.models.integration import IntegrationAccount, OAuthState, SyncAuditLog
from src.schemas.config import VerificationResult
from src.schemas.integration import (
    AuthUrlResponse,
    CodeExchangeRequest,
    IntegrationAccountResponse,
    SyncAuditLogResponse,
)
from src.services.config_service import ConfigService
from src.services.sync_service import run_sync_for_account

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations"])

OAUTH_STATE_TTL_MINUTES = 10


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("", response_model=list[IntegrationAccountResponse])
async def list_integrations(db: AsyncSession = Depends(get_db)):
    user = await get_or_create_default_user(db)
    q = select(IntegrationAccount).where(IntegrationAccount.user_id == user.id)
    res = await db.execute(q)
    return res.scalars().all()


@router.get("/{provider}/auth-url", response_model=AuthUrlResponse)
async def get_auth_url(provider: str, db: AsyncSession = Depends(get_db)):
    if provider not in ("polar", "concept2"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    user = await get_or_create_default_user(db)
    cid, csec, redir, _ = await ConfigService.get_provider_credentials(db, provider)
    if not cid or not csec:
        raise HTTPException(
            status_code=400,
            detail=f"{provider.capitalize()} credentials are not configured. Please enter Client ID & Secret in Settings.",
        )

    now = datetime.now(timezone.utc)
    # Prune expired OAuth states opportunistically
    await db.execute(delete(OAuthState).where(OAuthState.expires_at < now))

    state = secrets.token_urlsafe(32)
    oauth_state = OAuthState(
        state=state,
        user_id=user.id,
        provider=provider,
        expires_at=now + timedelta(minutes=OAUTH_STATE_TTL_MINUTES),
    )
    db.add(oauth_state)
    await db.flush()

    adapter: PolarAdapter | Concept2Adapter
    if provider == "polar":
        adapter = PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    else:
        adapter = Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)

    return AuthUrlResponse(auth_url=adapter.get_authorization_url(state))


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Handles OAuth 2.0 redirect callbacks from Polar and Concept2 with strict CSRF state validation."""
    if provider not in ("polar", "concept2"):
        return RedirectResponse(
            url="/config?status=error&message=Unsupported+provider",
            status_code=307,
        )

    if error:
        msg = redact_secrets(error_description or error)[:200]
        encoded_msg = urllib.parse.quote_plus(msg)
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message={encoded_msg}",
            status_code=307,
        )

    if not code:
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message=Missing+authorization+code",
            status_code=307,
        )

    if not state:
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message=Missing+OAuth+state+parameter",
            status_code=307,
        )

    # Atomically verify and consume single-use OAuth state nonce
    now = datetime.now(timezone.utc)
    st_res = await db.execute(
        select(OAuthState).where(
            OAuthState.state == state,
            OAuthState.provider == provider,
        )
    )
    stored_state = st_res.scalar_one_or_none()
    if not stored_state:
        logger.warning("Rejected OAuth callback for %s with unknown or replayed state", provider)
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message=Invalid+or+replayed+OAuth+state",
            status_code=307,
        )

    is_expired = _ensure_utc(stored_state.expires_at) < now
    state_user_id = stored_state.user_id
    await db.delete(stored_state)
    await db.flush()

    if is_expired:
        logger.warning("Rejected expired OAuth state for %s", provider)
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message=OAuth+authorization+expired.+Please+try+again.",
            status_code=307,
        )

    cid, csec, redir, _ = await ConfigService.get_provider_credentials(db, provider)
    if not cid or not csec:
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message=Provider+credentials+not+configured",
            status_code=307,
        )

    adapter: PolarAdapter | Concept2Adapter = (
        PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
        if provider == "polar"
        else Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    )

    try:
        token_data = await adapter.exchange_code(code)
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token")
        account_id = str(token_data.get("x_user_id") or token_data.get("user_id") or uuid.uuid4())

        if provider == "polar" and isinstance(adapter, PolarAdapter):
            try:
                await adapter.register_user(access_token, account_id)
            except Exception as reg_exc:
                logger.warning("Polar user registration notice: %s", redact_secrets(str(reg_exc)))

        q = select(IntegrationAccount).where(
            IntegrationAccount.user_id == state_user_id,
            IntegrationAccount.provider == provider,
        )
        res = await db.execute(q)
        account = res.scalar_one_or_none()

        if not account:
            account = IntegrationAccount(
                id=uuid.uuid4(),
                user_id=state_user_id,
                provider=provider,
                account_id=account_id,
                encrypted_access_token=encrypt_token(access_token),
                encrypted_refresh_token=encrypt_token(refresh_token) if refresh_token else None,
                is_active=True,
            )
            db.add(account)
        else:
            account.account_id = account_id
            account.encrypted_access_token = encrypt_token(access_token)
            if refresh_token:
                account.encrypted_refresh_token = encrypt_token(refresh_token)
            account.is_active = True

        await db.flush()
        return RedirectResponse(
            url=f"/config?status=connected&provider={provider}",
            status_code=307,
        )
    except Exception as exc:
        logger.error("OAuth callback exchange failed for %s: %s", provider, redact_secrets(str(exc)))
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message=Authorization+token+exchange+failed",
            status_code=307,
        )


@router.post("/{provider}/verify", response_model=VerificationResult)
async def verify_provider_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
):
    """Pings provider API, auto-refreshes expired tokens, and reports connection health."""
    if provider not in ("polar", "concept2"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    user = await get_or_create_default_user(db)
    cid, csec, redir, source = await ConfigService.get_provider_credentials(db, provider)
    if source == "decryption_error":
        return VerificationResult(
            provider=provider,
            is_connected=False,
            status="error",
            error_message="Stored client credentials could not be decrypted with ENCRYPTION_KEY. Please re-enter them in Settings.",
        )
    if not cid or not csec:
        return VerificationResult(
            provider=provider,
            is_connected=False,
            status="unconfigured",
            error_message="Client credentials not configured. Please enter Client ID & Secret.",
        )

    q = select(IntegrationAccount).where(
        IntegrationAccount.user_id == user.id,
        IntegrationAccount.provider == provider,
        IntegrationAccount.is_active.is_(True),
    )
    res = await db.execute(q)
    account = res.scalar_one_or_none()
    if not account:
        return VerificationResult(
            provider=provider,
            is_connected=False,
            status="unconfigured",
            error_message="No authorized account found. Please click 'Connect' to complete OAuth.",
        )

    access_token, token_err = decrypt_token_safe(account.encrypted_access_token, context=f"{provider}_access_token")
    if token_err or not access_token:
        return VerificationResult(
            provider=provider,
            is_connected=False,
            status="error",
            last_sync_at=account.last_sync_at,
            error_message="Stored OAuth token could not be decrypted. Please re-authorize via Connect.",
        )

    if provider == "polar":
        polar_adapter = PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
        diag = await polar_adapter.verify_connection(access_token, user_id=account.account_id)
        adapter: PolarAdapter | Concept2Adapter = polar_adapter
    else:
        c2_adapter = Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)
        diag = await c2_adapter.verify_connection(access_token)
        adapter = c2_adapter

    # If expired and refresh token exists, attempt refresh
    if diag["status"] == "expired" and account.encrypted_refresh_token:
        refresh_tok, ref_err = decrypt_token_safe(account.encrypted_refresh_token, context=f"{provider}_refresh_token")
        if not ref_err and refresh_tok:
            try:
                new_tokens = await adapter.refresh_access_token(refresh_tok)
                if "access_token" in new_tokens:
                    account.encrypted_access_token = encrypt_token(new_tokens["access_token"])
                    if "refresh_token" in new_tokens:
                        account.encrypted_refresh_token = encrypt_token(new_tokens["refresh_token"])
                    await db.flush()
                    if isinstance(adapter, PolarAdapter):
                        diag = await adapter.verify_connection(new_tokens["access_token"], user_id=account.account_id)
                    else:
                        diag = await adapter.verify_connection(new_tokens["access_token"])
            except Exception as ref_exc:
                logger.warning("Token refresh failed during verify for %s: %s", provider, redact_secrets(str(ref_exc)))

    return VerificationResult(
        provider=provider,
        is_connected=diag["is_connected"],
        status=diag["status"],
        athlete_name=diag.get("athlete_name"),
        last_sync_at=account.last_sync_at,
        error_message=diag.get("error"),
    )


@router.post("/{provider}/exchange-code", response_model=IntegrationAccountResponse)
async def exchange_oauth_code(
    provider: str,
    payload: CodeExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    if provider not in ("polar", "concept2"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    user = await get_or_create_default_user(db)
    cid, csec, redir, _ = await ConfigService.get_provider_credentials(db, provider)
    if not cid or not csec:
        raise HTTPException(status_code=400, detail=f"{provider.capitalize()} client credentials not configured")

    adapter: PolarAdapter | Concept2Adapter = (
        PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
        if provider == "polar"
        else Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    )

    try:
        token_data = await adapter.exchange_code(payload.code)
    except httpx.HTTPError as exc:
        logger.error("OAuth code exchange HTTP failure for %s: %s", provider, redact_secrets(str(exc)))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange authorization code with provider.",
        ) from exc

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token")
    account_id = str(token_data.get("x_user_id") or token_data.get("user_id") or uuid.uuid4())

    if isinstance(adapter, PolarAdapter):
        try:
            await adapter.register_user(access_token, account_id)
        except Exception as reg_exc:
            logger.warning("Polar user registration notice: %s", redact_secrets(str(reg_exc)))

    q = select(IntegrationAccount).where(
        IntegrationAccount.user_id == user.id,
        IntegrationAccount.provider == provider,
    )
    res = await db.execute(q)
    account = res.scalar_one_or_none()

    if not account:
        account = IntegrationAccount(
            id=uuid.uuid4(),
            user_id=user.id,
            provider=provider,
            account_id=account_id,
            encrypted_access_token=encrypt_token(access_token),
            encrypted_refresh_token=encrypt_token(refresh_token) if refresh_token else None,
            is_active=True,
        )
        db.add(account)
    else:
        account.account_id = account_id
        account.encrypted_access_token = encrypt_token(access_token)
        if refresh_token:
            account.encrypted_refresh_token = encrypt_token(refresh_token)
        account.is_active = True

    await db.flush()
    await db.refresh(account)
    return account


@router.post("/{provider}/sync", response_model=SyncAuditLogResponse, status_code=status.HTTP_200_OK)
async def trigger_sync(provider: str, db: AsyncSession = Depends(get_db)):
    if provider not in ("polar", "concept2"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    user = await get_or_create_default_user(db)
    q = select(IntegrationAccount).where(
        IntegrationAccount.user_id == user.id,
        IntegrationAccount.provider == provider,
        IntegrationAccount.is_active.is_(True),
    )
    res = await db.execute(q)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=f"No active integration found for provider: {provider}")

    audit_log = await run_sync_for_account(db, account, trigger_type="manual")
    return audit_log


@router.get("/sync-logs", response_model=list[SyncAuditLogResponse])
async def list_sync_logs(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    user = await get_or_create_default_user(db)
    q = (
        select(SyncAuditLog)
        .where(SyncAuditLog.user_id == user.id)
        .order_by(SyncAuditLog.started_at.desc())
        .limit(limit)
    )
    res = await db.execute(q)
    return res.scalars().all()
