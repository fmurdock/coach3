"""Integration tests for OAuth2 CSRF state nonce validation (US1, FR-006)."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.polar import PolarAdapter
from src.core.config import settings
from src.core.database import get_db
from src.main import app
from src.models.integration import IntegrationAccount, OAuthState


@pytest.mark.asyncio
async def test_oauth_callback_rejects_missing_forged_expired_and_replayed_state(
    db_session: AsyncSession,
    sample_user,
    monkeypatch,
):
    user, _ = sample_user
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(settings, "POLAR_CLIENT_ID", "polar_id")
    monkeypatch.setattr(settings, "POLAR_CLIENT_SECRET", "polar_secret")

    async def fake_exchange(self, code: str):
        return {"access_token": "tok_ok", "refresh_token": "ref_ok", "x_user_id": "999"}

    async def fake_register(self, access_token: str, member_id: str):
        return {"polar-user-id": member_id}

    monkeypatch.setattr(PolarAdapter, "exchange_code", fake_exchange)
    monkeypatch.setattr(PolarAdapter, "register_user", fake_register)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing state -> rejected
        r1 = await client.get("/api/v1/integrations/polar/callback?code=abc", follow_redirects=False)
        assert r1.status_code == 307
        assert "status=error" in r1.headers["location"]

        # 2. Forged state -> rejected
        r2 = await client.get("/api/v1/integrations/polar/callback?code=abc&state=forged123", follow_redirects=False)
        assert r2.status_code == 307
        assert "status=error" in r2.headers["location"]

        # 3. Expired state -> rejected
        expired = OAuthState(
            state="expired_state_tok",
            user_id=user.id,
            provider="polar",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(expired)
        await db_session.commit()
        r3 = await client.get(
            "/api/v1/integrations/polar/callback?code=abc&state=expired_state_tok",
            follow_redirects=False,
        )
        assert r3.status_code == 307
        assert "status=error" in r3.headers["location"]

        # Confirm zero accounts linked so far
        accs = (await db_session.execute(select(IntegrationAccount))).scalars().all()
        assert len(accs) == 0

        # 4. Valid state issued by auth-url -> succeeds once, then replay is rejected
        auth_resp = await client.get("/api/v1/integrations/polar/auth-url")
        assert auth_resp.status_code == 200
        auth_url = auth_resp.json()["auth_url"]
        state = parse_qs(urlparse(auth_url).query)["state"][0]

        r4 = await client.get(
            f"/api/v1/integrations/polar/callback?code=goodcode&state={state}",
            follow_redirects=False,
        )
        assert r4.status_code == 307
        assert "status=connected" in r4.headers["location"]

        # Replay exact same state -> rejected
        r5 = await client.get(
            f"/api/v1/integrations/polar/callback?code=goodcode&state={state}",
            follow_redirects=False,
        )
        assert r5.status_code == 307
        assert "status=error" in r5.headers["location"]
