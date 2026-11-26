"""API endpoints for single-user passphrase sign-in, sign-out, and auth status."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import (
    SESSION_COOKIE_NAME,
    check_login_rate_limit,
    clear_login_failures,
    create_session_token,
    get_client_ip,
    is_auth_configured,
    is_localhost_bypass_active,
    is_request_authenticated,
    is_request_https,
    record_failed_login,
    verify_configured_passphrase,
)
from src.core.config import settings
from src.core.database import get_db
from src.core.deps import get_or_create_default_user
from src.schemas.auth import AuthStatusResponse, LoginRequest

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Report current session authentication state."""
    user = await get_or_create_default_user(db)
    bypass = is_localhost_bypass_active(request)
    authenticated = is_request_authenticated(request)
    return AuthStatusResponse(
        authenticated=authenticated,
        auth_required=not bypass,
        localhost_bypass_active=bypass,
        passphrase_configured=is_auth_configured(user.passphrase_hash),
    )


@router.post("/login", response_model=AuthStatusResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with the single-user passphrase and issue an HttpOnly session cookie."""
    client_ip = get_client_ip(request)
    retry_after = check_login_rate_limit(client_ip)
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await get_or_create_default_user(db)
    if not is_auth_configured(user.passphrase_hash):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="COACH3_PASSPHRASE is not configured on the server.",
        )

    if not verify_configured_passphrase(payload.passphrase, db_passphrase_hash=user.passphrase_hash):
        lockout = record_failed_login(client_ip)
        if lockout > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later.",
                headers={"Retry-After": str(lockout)},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid passphrase.",
        )

    clear_login_failures(client_ip)
    token = create_session_token()
    max_age = settings.SESSION_TTL_DAYS * 86400
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=is_request_https(request),
        path="/",
    )
    return AuthStatusResponse(
        authenticated=True,
        auth_required=not is_localhost_bypass_active(request),
        localhost_bypass_active=is_localhost_bypass_active(request),
        passphrase_configured=True,
    )


@router.post("/logout")
async def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"status": "signed_out"}

