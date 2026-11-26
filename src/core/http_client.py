"""Shared HTTP client pooling, exponential backoff retries, and SSRF URL validation."""

import asyncio
import ipaddress
import logging
import random
import socket
from typing import Any
from urllib.parse import urlparse
import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

_shared_client: httpx.AsyncClient | None = None

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
BLOCKED_NETWORKS = (
    ipaddress.ip_network("169.254.0.0/16"),  # AWS/GCP/Azure metadata & IPv4 link-local
    ipaddress.ip_network("0.0.0.0/8"),       # "This host" unspecified network
    ipaddress.ip_network("100.64.0.0/10"),   # CGNAT / Alibaba metadata (100.100.100.200)
    ipaddress.ip_network("fe80::/10"),       # IPv6 link-local
    ipaddress.ip_network("::/128"),          # IPv6 unspecified
)
BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata.goog",
    "metadata",
    "instance-data",
}


def get_shared_http_client() -> httpx.AsyncClient:
    """Return a shared pooled AsyncClient (or create one lazily)."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            follow_redirects=False,
        )
    return _shared_client


async def close_shared_http_client() -> None:
    """Close the shared AsyncClient cleanly during application shutdown."""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = None


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return any(addr in net for net in BLOCKED_NETWORKS)


def validate_endpoint_url(url: str, *, allow_private_lan: bool = True) -> str:
    """Validate an external or local LLM endpoint URL to mitigate SSRF attacks.

    Allows http/https schemes (and localhost/LAN when allow_private_lan=True for homelab llama.cpp),
    while blocking non-HTTP schemes, cloud metadata endpoints, link-local ranges, and hosts outside
    optional settings.ALLOWED_LLM_HOSTS.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Endpoint URL must be a non-empty string.")
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed.")
    if not parsed.hostname:
        raise ValueError("Endpoint URL must include a valid hostname.")
    if parsed.username or parsed.password:
        raise ValueError("Endpoint URL must not embed userinfo credentials.")

    host = parsed.hostname.lower().rstrip(".")
    if host in BLOCKED_HOSTNAMES:
        raise ValueError(f"Endpoint host '{host}' is blocked for security reasons.")

    allowlist = settings.allowed_llm_hosts_list
    if allowlist and host not in allowlist:
        raise ValueError(f"Endpoint host '{host}' is not in ALLOWED_LLM_HOSTS.")

    # Direct IP literal check
    try:
        ipaddress.ip_address(host)
        if _is_blocked_ip(host):
            raise ValueError(f"Endpoint IP '{host}' is in a restricted metadata/link-local range.")
        if not allow_private_lan:
            addr = ipaddress.ip_address(host)
            if addr.is_private or addr.is_loopback or addr.is_reserved:
                raise ValueError(f"Endpoint IP '{host}' is not publicly routable.")
        return cleaned
    except ValueError as exc:
        if "restricted" in str(exc) or "publicly routable" in str(exc):
            raise

    # DNS resolution check (best effort; skip DNS failure for offline/mocked hostnames if allowlisted)
    if host not in ("localhost",):
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            for info in infos:
                ip_addr = str(info[4][0])
                if _is_blocked_ip(ip_addr):
                    raise ValueError(f"Endpoint host '{host}' resolves to restricted address '{ip_addr}'.")
        except socket.gaierror:
            # Allow unresolved hostnames to fail naturally at connect time (e.g. Docker DNS or unit tests)
            pass

    return cleaned


def _parse_retry_after(header_val: str | None, default_delay: float, max_delay: float = 30.0) -> float:
    if not header_val:
        return min(default_delay, max_delay)
    try:
        secs = float(header_val.strip())
        return max(0.0, min(secs, max_delay))
    except ValueError:
        return min(default_delay, max_delay)


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 3,
    base_delay_sec: float = 0.5,
    max_delay_sec: float = 30.0,
    **kwargs: Any,
) -> httpx.Response:
    """Execute an HTTP request with bounded exponential backoff + jitter on 429/5xx/timeouts."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
                jitter = random.uniform(0.0, 0.25)  # noqa: S311
                backoff = min(base_delay_sec * (2 ** (attempt - 1)) + jitter, max_delay_sec)
                delay = _parse_retry_after(resp.headers.get("Retry-After"), backoff, max_delay=max_delay_sec)
                logger.warning(
                    "Transient HTTP %s from %s (attempt %d/%d); retrying in %.2fs",
                    resp.status_code,
                    urlparse(url).netloc,
                    attempt,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            return resp
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt >= max_attempts:
                raise
            jitter = random.uniform(0.0, 0.25)  # noqa: S311
            delay = min(base_delay_sec * (2 ** (attempt - 1)) + jitter, max_delay_sec)
            logger.warning(
                "Transient network error %s for %s (attempt %d/%d); retrying in %.2fs",
                type(exc).__name__,
                urlparse(url).netloc,
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("request_with_retry exited unexpectedly")

