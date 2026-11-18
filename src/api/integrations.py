"""API endpoints for managing integrations, OAuth flows, and triggering syncs."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.polar import PolarAdapter
from src.adapters.concept2 import Concept2Adapter
from src.core.database import get_db
from src.core.security import encrypt_token
from src.models.integration import IntegrationAccount, SyncAuditLog
from src.models.user import User
from src.schemas.integration import (
    AuthUrlResponse,
    CodeExchangeRequest,
    IntegrationAccountResponse,
    SyncAuditLogResponse,
)
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
async def get_auth_url(provider: str):
    state = str(uuid.uuid4())
    if provider == "polar":
        adapter = PolarAdapter()
    elif provider == "concept2":
        adapter = Concept2Adapter()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    return AuthUrlResponse(auth_url=adapter.get_authorization_url(state))


@router.post("/{provider}/exchange-code", response_model=IntegrationAccountResponse)
async def exchange_oauth_code(
    provider: str,
    payload: CodeExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await get_or_create_default_user(db)
    if provider == "polar":
        adapter = PolarAdapter()
    elif provider == "concept2":
        adapter = Concept2Adapter()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    token_data = await adapter.exchange_code(payload.code)
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token")
    account_id = str(token_data.get("x_user_id") or token_data.get("user_id") or uuid.uuid4())

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
