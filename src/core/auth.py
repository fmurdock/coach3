"""Single-user passphrase authentication, signed session cookies, and brute-force throttling."""

from collections import defaultdict, deque
import hashlib
import hmac
import secrets
import time
from fastapi import Request

from src.core.config import settings

SESSION_COOKIE_NAME = "coach3_session"
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}

# Sliding-window brute-force limiter state (per client IP)
_FAILED_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)
_LOCKOUT_UNTIL: dict[str, float] = {}

MAX_ATTEMPTS_WINDOW = 5
WINDOW_SECONDS = 300.0  # 5 minutes
BASE_LOCKOUT_SECONDS = 60.0
MAX_LOCKOUT_SECONDS = 900.0  # 15 minutes


def hash_passphrase(passphrase: str, salt: bytes | None = None) -> str:
    """Hash a passphrase using stdlib scrypt (memory-hard KDF)."""
    salt_bytes = salt if salt is not None else secrets.token_bytes(16)
    derived = hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt_bytes,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt_bytes.hex()}${derived.hex()}"


def verify_passphrase(passphrase: str, stored_hash: str) -> bool:
    """Verify a plaintext passphrase against a stored scrypt hash in constant time."""
    if not passphrase or not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "scrypt":
        return False
    try:
        salt_bytes = bytes.fromhex(parts[1])
        expected_hex = parts[2]
    except ValueError:
        return False
    computed = hash_passphrase(passphrase, salt=salt_bytes).split("$")[2]
    return hmac.compare_digest(computed, expected_hex)


def verify_configured_passphrase(passphrase: str, db_passphrase_hash: str | None = None) -> bool:
    """Verify candidate passphrase against DB hash, COACH3_PASSPHRASE_HASH, or COACH3_PASSPHRASE."""
    if not passphrase:
        return False
    if db_passphrase_hash:
        return verify_passphrase(passphrase, db_passphrase_hash)
    if settings.COACH3_PASSPHRASE_HASH:
        return verify_passphrase(passphrase, settings.COACH3_PASSPHRASE_HASH)
    if settings.COACH3_PASSPHRASE:
        return hmac.compare_digest(passphrase, settings.COACH3_PASSPHRASE)
    return False


def is_auth_configured(db_passphrase_hash: str | None = None) -> bool:
    return bool(db_passphrase_hash or settings.COACH3_PASSPHRASE_HASH or settings.COACH3_PASSPHRASE)


def get_client_ip(request: Request) -> str:
    """Resolve client IP respecting X-Forwarded-For only when TRUST_PROXY_HEADERS is enabled."""
    if settings.TRUST_PROXY_HEADERS:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            first_ip = fwd.split(",")[0].strip()
            if first_ip:
                return first_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def is_request_https(request: Request) -> bool:
    """Determine if external client connection uses HTTPS (proxy-aware when trusted)."""
    if settings.TRUST_PROXY_HEADERS:
        proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        if proto:
            return proto == "https"
    return request.url.scheme == "https"


def is_loopback_request(request: Request) -> bool:
    """Return True strictly when the request originates from loopback/localhost."""
    client_ip = get_client_ip(request)
    if client_ip not in LOOPBACK_HOSTS:
        return False
    # If forwarded through a proxy from a non-loopback origin, do not treat as loopback
    if settings.TRUST_PROXY_HEADERS and request.headers.get("x-forwarded-for"):
        first = request.headers["x-forwarded-for"].split(",")[0].strip()
        if first not in LOOPBACK_HOSTS:
            return False
    return True


def is_localhost_bypass_active(request: Request) -> bool:
    """Localhost bypass is ONLY allowed in development/test mode for loopback clients when explicitly enabled."""
    env = settings.ENVIRONMENT.lower().strip()
    if env not in ("development", "test"):
        return False
    if not settings.AUTH_DISABLED_LOCALHOST:
        return False
    return is_loopback_request(request)


def _signing_secret() -> bytes:
    """Derive a dedicated session-signing key from ENCRYPTION_KEY."""
    return hashlib.sha256(f"coach3-session-v1:{settings.ENCRYPTION_KEY}".encode("utf-8")).digest()


def create_session_token(ttl_days: int | None = None) -> str:
    """Create a signed expiring HMAC-SHA256 session cookie token."""
    ttl = (ttl_days or settings.SESSION_TTL_DAYS) * 86400
    exp = int(time.time()) + ttl
    nonce = secrets.token_urlsafe(16)
    payload = f"v1.{exp}.{nonce}"
    sig = hmac.new(_signing_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session_token(token: str | None) -> bool:
    """Validate signature and expiration of a session cookie token."""
    if not token:
        return False
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        return False
    payload = f"{parts[0]}.{parts[1]}.{parts[2]}"
    provided_sig = parts[3]
    expected_sig = hmac.new(_signing_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return False
    try:
        exp = int(parts[1])
    except ValueError:
        return False
    return time.time() < exp


def is_request_authenticated(request: Request) -> bool:
    """Check if the current request carries a valid session cookie or qualifies for localhost dev bypass."""
    if is_localhost_bypass_active(request):
        return True
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return verify_session_token(token)


def check_login_rate_limit(client_ip: str) -> int:
    """Return remaining lockout seconds (0 if request is allowed)."""
    now = time.time()
    lock_until = _LOCKOUT_UNTIL.get(client_ip, 0.0)
    if lock_until > now:
        return max(1, int(lock_until - now))
    return 0


def record_failed_login(client_ip: str) -> int:
    """Record a failed login attempt and return lockout duration if threshold exceeded."""
    now = time.time()
    attempts = _FAILED_ATTEMPTS[client_ip]
    while attempts and (now - attempts[0]) > WINDOW_SECONDS:
        attempts.popleft()
    attempts.append(now)
    if len(attempts) >= MAX_ATTEMPTS_WINDOW:
        overage = len(attempts) - MAX_ATTEMPTS_WINDOW
        lockout = min(BASE_LOCKOUT_SECONDS * (2**overage), MAX_LOCKOUT_SECONDS)
        _LOCKOUT_UNTIL[client_ip] = now + lockout
        return int(lockout)
    return 0


def clear_login_failures(client_ip: str) -> None:
    _FAILED_ATTEMPTS.pop(client_ip, None)
    _LOCKOUT_UNTIL.pop(client_ip, None)


def reset_rate_limiter() -> None:
    """Reset in-memory rate limit buckets (used in tests)."""
    _FAILED_ATTEMPTS.clear()
    _LOCKOUT_UNTIL.clear()

