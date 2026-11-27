"""Dual-Engine LLM HTTP Clients for Google Gemini and local llama.cpp."""

import abc
import os
import re
import time
from typing import Optional
from urllib.parse import urlparse, urlunparse
import httpx

from src.core.http_client import request_with_retry, validate_endpoint_url
from src.core.logging import redact_secrets
from src.core.security import decrypt_token_safe
from src.schemas.coaching import ProviderHealthResponse


_TEST_FITNESS_PROMPT = "In one short sentence, explain Zone 2 cardio."


def _strip_json_fences(text: str) -> str:
    """Strip optional markdown code fences around JSON output."""
    cleaned = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```$", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return cleaned


def _is_running_in_docker() -> bool:
    """Return True when executing inside a Docker container."""
    return os.path.exists("/.dockerenv")


def _docker_host_fallback_url(url: str) -> Optional[str]:
    """Return a host.docker.internal equivalent when in Docker and targeting localhost."""
    if not _is_running_in_docker():
        return None
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        return None
    if host not in ("localhost", "127.0.0.1", "::1"):
        return None
    netloc = f"host.docker.internal:{parsed.port}" if parsed.port else "host.docker.internal"
    candidate = urlunparse(parsed._replace(netloc=netloc))
    try:
        return validate_endpoint_url(candidate, allow_private_lan=True)
    except ValueError:
        return None


def _docker_localhost_hint(url: str) -> str:
    """Return a helpful hint if running inside Docker and targeting localhost."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    if host in ("localhost", "127.0.0.1", "::1") and _is_running_in_docker():
        return " (Running inside Docker? Use host.docker.internal or your LAN IP instead of localhost.)"
    return ""


class BaseLLMClient(abc.ABC):
    @abc.abstractmethod
    async def test_connection(self) -> ProviderHealthResponse:
        """Tests live connectivity and measures round-trip inference latency."""
        pass

    @abc.abstractmethod
    async def generate_structured(self, system_prompt: str, user_prompt: str) -> str:
        """Generates structured JSON response from the LLM."""
        pass


class GeminiClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout_sec: float = 30.0,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_sec = timeout_sec
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    def _endpoint(self) -> str:
        return f"{self.base_url}/{self.model_name}:generateContent"

    async def test_connection(self) -> ProviderHealthResponse:
        t0 = time.perf_counter()
        try:
            url = self._endpoint()
            payload = {
                "contents": [{"role": "user", "parts": [{"text": _TEST_FITNESS_PROMPT}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 128,
                },
            }
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await request_with_retry(
                    client,
                    "POST",
                    url,
                    headers=self._headers(),
                    json=payload,
                    max_attempts=2,
                )
                lat = (time.perf_counter() - t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                    reply_text = str(parts[0].get("text", "")).strip() if parts else ""
                    if not reply_text:
                        return ProviderHealthResponse(
                            status="error",
                            latency_ms=round(lat, 1),
                            message=f"Google Gemini ({self.model_name}) returned an empty response.",
                        )
                    preview = redact_secrets(reply_text[:80])
                    return ProviderHealthResponse(
                        status="healthy",
                        latency_ms=round(lat, 1),
                        message=f"Connected to Google Gemini ({self.model_name}) in {lat:.1f}ms — \"{preview}\"",
                    )
                elif resp.status_code in (401, 403):
                    return ProviderHealthResponse(
                        status="invalid_credentials",
                        latency_ms=round(lat, 1),
                        message=f"Gemini authentication failed ({resp.status_code}): Invalid API key",
                    )
                else:
                    safe_body = redact_secrets(resp.text[:120])
                    return ProviderHealthResponse(
                        status="error",
                        latency_ms=round(lat, 1),
                        message=f"Gemini API returned status {resp.status_code}: {safe_body}",
                    )
        except Exception as e:
            lat = (time.perf_counter() - t0) * 1000
            return ProviderHealthResponse(
                status="unreachable",
                latency_ms=round(lat, 1),
                message=f"Gemini connection failed: {redact_secrets(str(e))}",
            )

    async def generate_structured(self, system_prompt: str, user_prompt: str) -> str:
        url = self._endpoint()
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json",
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await request_with_retry(
                client,
                "POST",
                url,
                headers=self._headers(),
                json=payload,
                max_attempts=3,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Gemini API error ({resp.status_code}): {redact_secrets(resp.text[:250])}"
                )
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini API returned zero candidates")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini candidate contains zero parts")
            return str(parts[0].get("text", ""))


class LlamaCppClient(BaseLLMClient):
    def __init__(
        self,
        endpoint_url: str,
        model_name: str = "qwen2.5-14b-instruct",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout_sec: float = 60.0,
    ):
        validated = validate_endpoint_url(endpoint_url, allow_private_lan=True)
        base = validated.rstrip("/")
        if base.endswith("/chat/completions"):
            self.completions_url = base
        elif base.endswith("/v1"):
            self.completions_url = f"{base}/chat/completions"
        else:
            self.completions_url = f"{base}/v1/chat/completions"

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_sec = timeout_sec

    async def _post_completions(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
        *,
        max_attempts: int,
    ) -> httpx.Response:
        """POST chat completions, falling back to host.docker.internal when running in Docker."""
        original_url = self.completions_url
        fallback_url = _docker_host_fallback_url(original_url)
        try:
            return await request_with_retry(
                client,
                "POST",
                original_url,
                json=payload,
                max_attempts=1 if fallback_url else max_attempts,
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            if not fallback_url:
                raise
            try:
                resp = await request_with_retry(
                    client,
                    "POST",
                    fallback_url,
                    json=payload,
                    max_attempts=max_attempts,
                )
            except (httpx.ConnectError, httpx.TimeoutException) as fallback_exc:
                raise RuntimeError(
                    f"Local LLM server unreachable at {original_url} (and {fallback_url} from Docker): "
                    f"{redact_secrets(str(fallback_exc))}. Ensure a local LLM server (e.g., llama.cpp, "
                    "Ollama, LM Studio) is running on the host and listening on that port."
                ) from fallback_exc
            self.completions_url = fallback_url
            return resp

    async def test_connection(self) -> ProviderHealthResponse:
        t0 = time.perf_counter()
        try:
            payload: dict[str, object] = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": _TEST_FITNESS_PROMPT}
                ],
                "temperature": 0.2,
                "max_tokens": 64,
            }
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await self._post_completions(client, payload, max_attempts=2)
                lat = (time.perf_counter() - t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    reply_text = str(choices[0].get("message", {}).get("content", "")).strip() if choices else ""
                    if not reply_text:
                        return ProviderHealthResponse(
                            status="error",
                            latency_ms=round(lat, 1),
                            message=f"llama.cpp ({self.model_name}) returned an empty response.",
                        )
                    preview = redact_secrets(reply_text[:80])
                    return ProviderHealthResponse(
                        status="healthy",
                        latency_ms=round(lat, 1),
                        message=f"Connected to local llama.cpp ({self.model_name}) in {lat:.1f}ms — \"{preview}\"",
                    )
                else:
                    safe_body = redact_secrets(resp.text[:120])
                    return ProviderHealthResponse(
                        status="error",
                        latency_ms=round(lat, 1),
                        message=f"llama.cpp server returned status {resp.status_code}: {safe_body}",
                    )
        except Exception as e:
            lat = (time.perf_counter() - t0) * 1000
            err_msg = str(e)
            if isinstance(e, RuntimeError) and "from Docker" in err_msg:
                return ProviderHealthResponse(
                    status="unreachable",
                    latency_ms=round(lat, 1),
                    message=err_msg,
                )
            hint = _docker_localhost_hint(self.completions_url)
            return ProviderHealthResponse(
                status="unreachable",
                latency_ms=round(lat, 1),
                message=f"llama.cpp server unreachable at {self.completions_url}: {redact_secrets(err_msg)}{hint}",
            )

    async def generate_structured(self, system_prompt: str, user_prompt: str) -> str:
        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await self._post_completions(client, payload, max_attempts=3)
            if resp.status_code in (400, 422):
                # Some llama.cpp / OpenAI-compatible servers reject response_format
                fallback_payload = {k: v for k, v in payload.items() if k != "response_format"}
                resp = await self._post_completions(client, fallback_payload, max_attempts=2)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"llama.cpp server error ({resp.status_code}): {redact_secrets(resp.text[:250])}"
                )
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("llama.cpp returned zero choices")
            return _strip_json_fences(str(choices[0].get("message", {}).get("content", "")))


async def list_local_models(endpoint_url: str, timeout_sec: float = 10.0) -> list[str]:
    """Query a local OpenAI-compatible / llama.cpp server for installed model IDs."""
    validated = validate_endpoint_url(endpoint_url, allow_private_lan=True)
    base = validated.rstrip("/")
    for suffix in ("/v1/chat/completions", "/chat/completions", "/v1/models", "/models"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    models_url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"

    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        try:
            resp = await request_with_retry(client, "GET", models_url, max_attempts=2)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
            fallback_url = _docker_host_fallback_url(models_url)
            if fallback_url:
                resp = await request_with_retry(client, "GET", fallback_url, max_attempts=2)
            else:
                raise RuntimeError(
                    f"Could not reach local LLM server at {models_url}: {redact_secrets(str(exc))}"
                ) from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"Local LLM server returned status {resp.status_code} from {models_url}: "
            f"{redact_secrets(resp.text[:160])}"
        )

    payload = resp.json()
    models: list[str] = []
    if isinstance(payload, dict):
        for item in payload.get("data") or []:
            if isinstance(item, dict) and item.get("id"):
                models.append(str(item["id"]))
        if not models:
            for item in payload.get("models") or []:
                if isinstance(item, dict) and (item.get("id") or item.get("name")):
                    models.append(str(item.get("id") or item.get("name")))
    return models


def get_llm_client_for_config(
    provider_type: str,
    endpoint_url: str,
    api_key_encrypted: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    raw_api_key: Optional[str] = None,
) -> BaseLLMClient:
    """Instantiates a client for the given provider configuration."""
    if provider_type == "gemini":
        key = raw_api_key
        if not key and api_key_encrypted:
            decrypted, dec_err = decrypt_token_safe(api_key_encrypted, context="gemini_api_key")
            if dec_err:
                raise ValueError(
                    "Stored Gemini API key could not be decrypted with the current ENCRYPTION_KEY. "
                    "Please re-enter your API key in Settings."
                )
            key = decrypted
        return GeminiClient(
            api_key=key or "",
            model_name=model_name or "gemini-2.5-flash",
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
    elif provider_type == "llama_cpp":
        return LlamaCppClient(
            endpoint_url=endpoint_url or "http://localhost:8080/v1",
            model_name=model_name or "qwen2.5-14b-instruct",
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
    else:
        raise ValueError(f"Unsupported LLM provider type: {provider_type}")
