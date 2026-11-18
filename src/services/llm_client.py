"""Dual-Engine LLM HTTP Clients for Google Gemini and local llama.cpp."""

import abc
import json
import time
from typing import Any, Dict, Optional
import httpx

from src.core.security import decrypt_token, encrypt_token
from src.schemas.coaching import ProviderHealthResponse


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

    async def test_connection(self) -> ProviderHealthResponse:
        t0 = time.perf_counter()
        try:
            url = f"{self.base_url}/{self.model_name}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "Ping. Respond with {\"status\": \"ok\"}"}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 20,
                    "responseMimeType": "application/json",
                },
            }
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.post(url, json=payload)
                lat = (time.perf_counter() - t0) * 1000

                if resp.status_code == 200:
                    return ProviderHealthResponse(
                        status="healthy",
                        latency_ms=round(lat, 1),
                        message=f"Connected to Google Gemini ({self.model_name}) in {lat:.1f}ms",
                    )
                elif resp.status_code in (401, 403):
                    return ProviderHealthResponse(
                        status="invalid_credentials",
                        latency_ms=round(lat, 1),
                        message=f"Gemini authentication failed ({resp.status_code}): Invalid API key",
                    )
                else:
                    return ProviderHealthResponse(
                        status="error",
                        latency_ms=round(lat, 1),
                        message=f"Gemini API returned status {resp.status_code}: {resp.text[:100]}",
                    )
        except Exception as e:
            lat = (time.perf_counter() - t0) * 1000
            return ProviderHealthResponse(
                status="unreachable",
                latency_ms=round(lat, 1),
                message=f"Gemini connection failed: {str(e)}",
            )

    async def generate_structured(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/{self.model_name}:generateContent?key={self.api_key}"
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
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Gemini API error ({resp.status_code}): {resp.text}"
                )
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini API returned zero candidates")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini candidate contains zero parts")
            return parts[0].get("text", "")


class LlamaCppClient(BaseLLMClient):
    def __init__(
        self,
        endpoint_url: str,
        model_name: str = "qwen2.5-14b-instruct",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout_sec: float = 60.0,
    ):
        base = endpoint_url.rstrip("/")
        if not base.endswith("/v1"):
            self.completions_url = f"{base}/v1/chat/completions"
        else:
            self.completions_url = f"{base}/chat/completions"

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_sec = timeout_sec

    async def test_connection(self) -> ProviderHealthResponse:
        t0 = time.perf_counter()
        try:
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": "Ping. Respond with {\"status\": \"ok\"}"}
                ],
                "temperature": 0.1,
                "max_tokens": 20,
                "response_format": {"type": "json_object"},
            }
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.post(self.completions_url, json=payload)
                lat = (time.perf_counter() - t0) * 1000

                if resp.status_code == 200:
                    return ProviderHealthResponse(
                        status="healthy",
                        latency_ms=round(lat, 1),
                        message=f"Connected to local llama.cpp ({self.model_name}) in {lat:.1f}ms",
                    )
                else:
                    return ProviderHealthResponse(
                        status="error",
                        latency_ms=round(lat, 1),
                        message=f"llama.cpp server returned status {resp.status_code}: {resp.text[:100]}",
                    )
        except Exception as e:
            lat = (time.perf_counter() - t0) * 1000
            return ProviderHealthResponse(
                status="unreachable",
                latency_ms=round(lat, 1),
                message=f"llama.cpp server unreachable at {self.completions_url}: {str(e)}",
            )

    async def generate_structured(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
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
            resp = await client.post(self.completions_url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"llama.cpp server error ({resp.status_code}): {resp.text}"
                )
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("llama.cpp returned zero choices")
            return choices[0].get("message", {}).get("content", "")


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
            try:
                key = decrypt_token(api_key_encrypted)
            except Exception:
                key = ""
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
