"""Unit tests for Dual-Engine LLM clients (Gemini and llama.cpp)."""

import json
import httpx
import pytest

from src.core.security import encrypt_token
from src.services.llm_client import (
    GeminiClient,
    LlamaCppClient,
    get_llm_client_for_config,
)


@pytest.mark.asyncio
async def test_gemini_client_test_connection_healthy(monkeypatch):
    client = GeminiClient(api_key="test-api-key", model_name="gemini-2.5-flash")

    def mock_handler(request: httpx.Request):
        assert "key=test-api-key" in str(request.url)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{\"status\":\"ok\"}"}]}}]})

    mock_transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def get_mock_client(*args, **kwargs):
        kwargs["transport"] = mock_transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", get_mock_client)

    health = await client.test_connection()
    assert health.status == "healthy"
    assert "Google Gemini" in health.message


@pytest.mark.asyncio
async def test_gemini_client_invalid_credentials(monkeypatch):
    client = GeminiClient(api_key="bad-key")

    def mock_handler(request: httpx.Request):
        return httpx.Response(403, json={"error": {"message": "Invalid API key"}})

    mock_transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def get_mock_client(*args, **kwargs):
        kwargs["transport"] = mock_transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", get_mock_client)

    health = await client.test_connection()
    assert health.status == "invalid_credentials"
    assert "Invalid API key" in health.message


@pytest.mark.asyncio
async def test_llama_cpp_client_healthy(monkeypatch):
    client = LlamaCppClient(endpoint_url="http://localhost:8080/v1", model_name="qwen2.5-14b")

    def mock_handler(request: httpx.Request):
        assert str(request.url).endswith("/v1/chat/completions")
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"status\": \"ok\"}"}}]})

    mock_transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def get_mock_client(*args, **kwargs):
        kwargs["transport"] = mock_transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", get_mock_client)

    health = await client.test_connection()
    assert health.status == "healthy"
    assert "llama.cpp" in health.message


def test_get_llm_client_for_config():
    encrypted_key = encrypt_token("my-secret-gemini-key")
    gemini = get_llm_client_for_config(
        provider_type="gemini",
        endpoint_url="https://generativelanguage.googleapis.com",
        api_key_encrypted=encrypted_key,
        model_name="gemini-2.5-flash",
    )
    assert isinstance(gemini, GeminiClient)
    assert gemini.api_key == "my-secret-gemini-key"

    llama = get_llm_client_for_config(
        provider_type="llama_cpp",
        endpoint_url="http://192.168.1.100:8080",
        model_name="mistral-7b",
    )
    assert isinstance(llama, LlamaCppClient)
    assert llama.completions_url == "http://192.168.1.100:8080/v1/chat/completions"

    with pytest.raises(ValueError):
        get_llm_client_for_config(
            provider_type="unsupported_provider",
            endpoint_url="http://unknown",
        )
