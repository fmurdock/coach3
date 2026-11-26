"""Security, authentication, CORS, CSP, SSRF, secret redaction, and health tests (US1)."""

from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import (
    SESSION_COOKIE_NAME,
    hash_passphrase,
    reset_rate_limiter,
    verify_passphrase,
)
from src.core.config import INSECURE_EXAMPLE_ENCRYPTION_KEY, Settings, settings
from src.core.database import get_db
from src.core.http_client import validate_endpoint_url
from src.core.logging import redact_secrets
from src.core.security import decrypt_token_safe, encrypt_token
from src.main import app
from src.services.llm_client import GeminiClient, LlamaCppClient


def test_settings_rejects_missing_or_example_encryption_key_in_production():
    with pytest.raises(ValueError, match="ENCRYPTION_KEY is required"):
        Settings(_env_file=None, ENVIRONMENT="production", ENCRYPTION_KEY="")

    with pytest.raises(ValueError, match="insecure example placeholder"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            ENCRYPTION_KEY=INSECURE_EXAMPLE_ENCRYPTION_KEY,
        )

    valid_key = Fernet.generate_key().decode("utf-8")
    cfg = Settings(_env_file=None, ENVIRONMENT="production", ENCRYPTION_KEY=valid_key)
    assert cfg.ENCRYPTION_KEY == valid_key


def test_scrypt_passphrase_hash_and_verify():
    hashed = hash_passphrase("correct-horse-battery-staple")
    assert hashed.startswith("scrypt$")
    assert verify_passphrase("correct-horse-battery-staple", hashed) is True
    assert verify_passphrase("wrong-passphrase", hashed) is False


def test_decrypt_token_safe_handles_invalid_key_gracefully():
    key1 = Fernet.generate_key().decode("utf-8")
    key2 = Fernet.generate_key().decode("utf-8")
    cipher = encrypt_token("my-secret-value", key=key1)

    plain, err = decrypt_token_safe(cipher, key=key1)
    assert plain == "my-secret-value"
    assert err is False

    plain_bad, err_bad = decrypt_token_safe(cipher, key=key2)
    assert plain_bad is None
    assert err_bad is True


def test_ssrf_endpoint_validation_blocks_metadata_and_bad_schemes():
    assert validate_endpoint_url("http://localhost:8080/v1") == "http://localhost:8080/v1"
    assert validate_endpoint_url("http://192.168.1.50:8080/v1") == "http://192.168.1.50:8080/v1"

    with pytest.raises(ValueError, match="restricted"):
        validate_endpoint_url("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(ValueError, match="blocked"):
        validate_endpoint_url("http://metadata.google.internal/computeMetadata/v1/")

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_endpoint_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="restricted"):
        LlamaCppClient(endpoint_url="http://169.254.169.254/v1")


def test_gemini_client_uses_header_not_query_param_and_redacts_secrets():
    client = GeminiClient(api_key="AIzaSySuperSecretKey1234567890")
    assert "?key=" not in client._endpoint()
    assert "AIzaSySuperSecretKey1234567890" not in client._endpoint()
    assert client._headers()["x-goog-api-key"] == "AIzaSySuperSecretKey1234567890"

    redacted = redact_secrets("Bearer tok12345 key=abc123 AIzaSySuperSecretKey1234567890")
    assert "tok12345" not in redacted
    assert "abc123" not in redacted
    assert "AIzaSySuperSecretKey1234567890" not in redacted


@pytest.mark.asyncio
async def test_auth_login_cookie_rate_limit_and_protection(db_session: AsyncSession, monkeypatch):
    reset_rate_limiter()
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_DISABLED_LOCALHOST", False)
    monkeypatch.setattr(settings, "COACH3_PASSPHRASE", "ultra-secret-pass")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated API returns 401
        r_api = await client.get("/api/v1/workouts")
        assert r_api.status_code == 401

        # Unauthenticated HTML redirects to /login
        r_ui = await client.get("/dashboard", follow_redirects=False)
        assert r_ui.status_code == 307
        assert r_ui.headers["location"].startswith("/login")

        # Security headers & strict CSP present
        r_login = await client.get("/login")
        assert r_login.status_code == 200
        assert r_login.headers["x-content-type-options"] == "nosniff"
        assert r_login.headers["x-frame-options"] == "DENY"
        assert r_login.headers["referrer-policy"] == "no-referrer"
        assert "script-src 'self'" in r_login.headers["content-security-policy"]
        assert "x-request-id" in r_login.headers

        # Brute-force wrong passphrase triggers 429 on 5th failed attempt
        for i in range(4):
            bad = await client.post("/api/v1/auth/login", json={"passphrase": f"wrong-{i}"})
            assert bad.status_code == 401
        locked = await client.post("/api/v1/auth/login", json={"passphrase": "wrong-final"})
        assert locked.status_code == 429
        assert "retry-after" in locked.headers

        # Reset limiter, sign in with valid passphrase, verify cookie unlocks API
        reset_rate_limiter()
        ok = await client.post("/api/v1/auth/login", json={"passphrase": "ultra-secret-pass"})
        assert ok.status_code == 200
        assert SESSION_COOKIE_NAME in ok.cookies
        set_cookie = ok.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie
        assert "samesite=lax" in set_cookie

        r_authed = await client.get("/api/v1/workouts")
        assert r_authed.status_code == 200

        # Sign out revokes access
        await client.post("/api/v1/auth/logout")
        r_after = await client.get("/api/v1/workouts")
        assert r_after.status_code == 401

    reset_rate_limiter()


@pytest.mark.asyncio
async def test_cors_blocks_untrusted_origin(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health", headers={"Origin": "https://evil.example"})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_health_returns_503_when_db_unreachable():
    class BrokenSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("DB connection refused")

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "unreachable"
