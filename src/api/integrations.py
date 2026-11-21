"""API endpoints for managing integrations, OAuth flows, and triggering syncs."""

import urllib.parse
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.polar import PolarAdapter
from src.adapters.concept2 import Concept2Adapter
from src.core.database import get_db
from src.core.security import decrypt_token, encrypt_token
from src.models.integration import IntegrationAccount, SyncAuditLog
from src.models.user import User
from src.schemas.config import VerificationResult
from src.schemas.integration import (
    AuthUrlResponse,
    CodeExchangeRequest,
    IntegrationAccountResponse,
    SyncAuditLogResponse,
)
from src.services.config_service import ConfigService
from src.services.sync_service import run_sync_for_account

router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations"])


async def get_or_create_default_user(db: AsyncSession) -> User:
    """Helper for single-user self-hosted mode: retrieves or seeds default user."""
    res = await db.execute(select(User))
    user = res.scalars().first()
    if not user:
        user = User(id=uuid.uuid4())
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.get("", response_model=list[IntegrationAccountResponse])
async def list_integrations(db: AsyncSession = Depends(get_db)):
    user = await get_or_create_default_user(db)
    q = select(IntegrationAccount).where(IntegrationAccount.user_id == user.id)
    res = await db.execute(q)
    return res.scalars().all()


@router.get("/{provider}/auth-url", response_model=AuthUrlResponse)
async def get_auth_url(provider: str, db: AsyncSession = Depends(get_db)):
    state = str(uuid.uuid4())
    cid, csec, redir, _ = await ConfigService.get_provider_credentials(db, provider)
    if not cid or not csec:
        raise HTTPException(
            status_code=400,
            detail=f"{provider.capitalize()} credentials are not configured. Please enter Client ID & Secret in Settings.",
        )

    if provider == "polar":
        adapter = PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    elif provider == "concept2":
        adapter = Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

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
    """Handles OAuth 2.0 redirect callbacks from Polar and Concept2 and redirects to /config."""
    if error:
        msg = error_description or error
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

    user = await get_or_create_default_user(db)
    cid, csec, redir, _ = await ConfigService.get_provider_credentials(db, provider)
    if not cid or not csec:
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message=Provider+credentials+not+configured",
            status_code=307,
        )

    if provider == "polar":
        adapter = PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    elif provider == "concept2":
        adapter = Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    else:
        return RedirectResponse(
            url="/config?status=error&message=Unsupported+provider",
            status_code=307,
        )

    try:
        token_data = await adapter.exchange_code(code)
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token")
        account_id = str(token_data.get("x_user_id") or token_data.get("user_id") or uuid.uuid4())

        if provider == "polar":
            try:
                await adapter.register_user(access_token, account_id)
            except Exception:
                pass

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

        await db.commit()
        return RedirectResponse(
            url=f"/config?status=connected&provider={provider}",
            status_code=307,
        )
    except Exception as exc:
        encoded_err = urllib.parse.quote_plus(str(exc))
        return RedirectResponse(
            url=f"/config?status=error&provider={provider}&message={encoded_err}",
            status_code=307,
        )


@router.post("/{provider}/verify", response_model=VerificationResult)
async def verify_provider_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
):
    """Pings provider API, auto-refreshes expired tokens, and reports connection health."""
    user = await get_or_create_default_user(db)
    cid, csec, redir, _ = await ConfigService.get_provider_credentials(db, provider)
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
        IntegrationAccount.is_active == True,
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

    access_token = decrypt_token(account.encrypted_access_token)
    if provider == "polar":
        adapter = PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
        diag = await adapter.verify_connection(access_token, user_id=account.account_id)
    elif provider == "concept2":
        adapter = Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)
        diag = await adapter.verify_connection(access_token)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # If expired and refresh token exists, attempt refresh
    if diag["status"] == "expired" and account.encrypted_refresh_token:
        refresh_tok = decrypt_token(account.encrypted_refresh_token)
        try:
            new_tokens = await adapter.refresh_access_token(refresh_tok)
            if "access_token" in new_tokens:
                account.encrypted_access_token = encrypt_token(new_tokens["access_token"])
                if "refresh_token" in new_tokens:
                    account.encrypted_refresh_token = encrypt_token(new_tokens["refresh_token"])
                await db.commit()
                if provider == "polar":
                    diag = await adapter.verify_connection(new_tokens["access_token"], user_id=account.account_id)
                else:
                    diag = await adapter.verify_connection(new_tokens["access_token"])
        except Exception:
            pass

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
    user = await get_or_create_default_user(db)
    cid, csec, redir, _ = await ConfigService.get_provider_credentials(db, provider)
    if provider == "polar":
        adapter = PolarAdapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    elif provider == "concept2":
        adapter = Concept2Adapter(client_id=cid, client_secret=csec, redirect_uri=redir)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    token_data = await adapter.exchange_code(payload.code)
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token")
    account_id = str(token_data.get("x_user_id") or token_data.get("user_id") or uuid.uuid4())

    if provider == "polar":
        try:
            await adapter.register_user(access_token, account_id)
        except Exception:
            pass

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

    await db.commit()
    await db.refresh(account)
    return account


@router.post("/{provider}/sync", response_model=SyncAuditLogResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(provider: str, db: AsyncSession = Depends(get_db)):
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
async def list_sync_logs(limit: int = 20, db: AsyncSession = Depends(get_db)):
    user = await get_or_create_default_user(db)
    q = select(SyncAuditLog).where(SyncAuditLog.user_id == user.id).order_by(SyncAuditLog.started_at.desc()).limit(limit)
    res = await db.execute(q)
    return res.scalars().all()
