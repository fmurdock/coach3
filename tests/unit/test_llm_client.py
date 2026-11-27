"""Unit tests for Dual-Engine LLM clients (Gemini and llama.cpp)."""

import httpx
import pytest

from src.core.security import encrypt_token
from src.services.llm_client import (
    GeminiClient,
    LlamaCppClient,
    get_llm_client_for_config,
    list_local_models,
)


@pytest.mark.asyncio
async def test_gemini_client_test_connection_healthy(monkeypatch):
    client = GeminiClient(api_key="test-api-key", model_name="gemini-2.5-flash")

    def mock_handler(request: httpx.Request):
        assert request.headers.get("x-goog-api-key") == "test-api-key"
        assert "key=" not in str(request.url)
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


@pytest.mark.asyncio
async def test_llm_short_fitness_prompt_returns_output(monkeypatch):
    """Send a short fitness-relevant prompt to both Gemini and llama.cpp clients and expect non-empty output."""
    short_prompt = "In one short sentence, explain Zone 2 cardio."

    # 1. GeminiClient
    gemini = GeminiClient(api_key="test-key", model_name="gemini-2.5-flash")

    def gemini_handler(request: httpx.Request):
        body = request.content.decode("utf-8")
        assert "Zone 2" in body
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Zone 2 cardio is steady aerobic exercise at 60-70% of max heart rate."}
                            ]
                        }
                    }
                ]
            },
        )

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(*a, **{**kw, "transport": httpx.MockTransport(gemini_handler)}),
    )
    gemini_out = await gemini.generate_structured("Be concise.", short_prompt)
    assert isinstance(gemini_out, str)
    assert len(gemini_out.strip()) > 0
    assert "Zone 2" in gemini_out

    # 2. LlamaCppClient
    llama = LlamaCppClient(endpoint_url="http://localhost:8080/v1/chat/completions", model_name="qwen2.5-14b")
    assert llama.completions_url == "http://localhost:8080/v1/chat/completions"

    def llama_handler(request: httpx.Request):
        body = request.content.decode("utf-8")
        assert "Zone 2" in body
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "```json\n{\"summary\": \"Zone 2 builds mitochondrial density.\"}\n```"
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(*a, **{**kw, "transport": httpx.MockTransport(llama_handler)}),
    )
    llama_out = await llama.generate_structured("Return JSON.", short_prompt)
    assert llama_out == '{"summary": "Zone 2 builds mitochondrial density."}'


@pytest.mark.asyncio
async def test_llama_cpp_empty_output_and_response_format_fallback(monkeypatch):
    llama = LlamaCppClient(endpoint_url="http://192.168.1.50:8080", model_name="local-model")
    real_async_client = httpx.AsyncClient

    # Empty choice text on test_connection must report error rather than false healthy
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(
            *a,
            **{
                **kw,
                "transport": httpx.MockTransport(
                    lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})
                ),
            },
        ),
    )
    health = await llama.test_connection()
    assert health.status == "error"
    assert "empty response" in health.message.lower()

    # 400 on response_format falls back cleanly to plain payload
    calls = {"count": 0}

    def fallback_handler(request: httpx.Request):
        calls["count"] += 1
        body = request.content.decode("utf-8")
        if '"response_format"' in body:
            return httpx.Response(400, json={"error": "response_format unsupported"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"ok\": true}"}}]})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(*a, **{**kw, "transport": httpx.MockTransport(fallback_handler)}),
    )
    out = await llama.generate_structured("sys", "usr")
    assert out == '{"ok": true}'
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_live_llm_server_optional_smoke():
    """Optional live smoke test: set LIVE_LLM_TEST_URL (or LIVE_GEMINI_API_KEY) to run against a real server."""
    import os

    live_url = os.environ.get("LIVE_LLM_TEST_URL")
    live_gemini_key = os.environ.get("LIVE_GEMINI_API_KEY")
    if not live_url and not live_gemini_key:
        pytest.skip("Set LIVE_LLM_TEST_URL or LIVE_GEMINI_API_KEY to run live LLM prompt smoke test")

    if live_url:
        client = LlamaCppClient(
            endpoint_url=live_url,
            model_name=os.environ.get("LIVE_LLM_MODEL", "qwen2.5-14b-instruct"),
        )
        health = await client.test_connection()
        assert health.status == "healthy", health.message
    if live_gemini_key:
        g_client = GeminiClient(
            api_key=live_gemini_key,
            model_name=os.environ.get("LIVE_GEMINI_MODEL", "gemini-2.5-flash"),
        )
        health = await g_client.test_connection()
        assert health.status == "healthy", health.message


@pytest.mark.asyncio
async def test_list_local_models_parses_openai_and_normalizes_url(monkeypatch):
    real_async_client = httpx.AsyncClient
    captured_urls = []

    def handler(request: httpx.Request):
        captured_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "Qwen2.5-14B-Instruct-Q4_K_M"},
                    {"id": "gemma-4-12b-it-Q4_K_M"},
                ]
            },
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(*a, **{**kw, "transport": httpx.MockTransport(handler)}),
    )
    models = await list_local_models("http://localhost:8080/v1/chat/completions")
    assert captured_urls == ["http://localhost:8080/v1/models"]
    assert models == ["Qwen2.5-14B-Instruct-Q4_K_M", "gemma-4-12b-it-Q4_K_M"]


@pytest.mark.asyncio
async def test_llama_cpp_docker_localhost_fallback_succeeds(monkeypatch):
    """When inside Docker and localhost fails, LlamaCppClient falls back to host.docker.internal."""
    monkeypatch.setattr("src.services.llm_client._is_running_in_docker", lambda: True)
    seen_urls: list[str] = []
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request):
        seen_urls.append(str(request.url))
        if request.url.host in ("localhost", "127.0.0.1"):
            raise httpx.ConnectError("Connection refused", request=request)
        if request.url.host == "host.docker.internal":
            return httpx.Response(200, json={"choices": [{"message": {"content": "Zone 2 builds aerobic base."}}]})
        raise AssertionError(f"Unexpected host: {request.url.host}")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(*a, **{**kw, "transport": httpx.MockTransport(handler)}),
    )

    client = LlamaCppClient(endpoint_url="http://localhost:8080/v1", model_name="qwen2.5-14b")
    health = await client.test_connection()
    assert health.status == "healthy"
    assert "llama.cpp" in health.message
    assert seen_urls == [
        "http://localhost:8080/v1/chat/completions",
        "http://host.docker.internal:8080/v1/chat/completions",
    ]
    assert client.completions_url == "http://host.docker.internal:8080/v1/chat/completions"

    # Also verify generate_structured falls back for 127.0.0.1 and handles 400 response_format afterwards
    seen_urls.clear()
    client2 = LlamaCppClient(endpoint_url="http://127.0.0.1:11434/v1", model_name="llama3")

    def structured_handler(request: httpx.Request):
        seen_urls.append(str(request.url))
        if request.url.host == "127.0.0.1":
            raise httpx.ConnectError("Connection refused", request=request)
        if b'"response_format"' in request.content:
            return httpx.Response(400, json={"error": "unsupported"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(*a, **{**kw, "transport": httpx.MockTransport(structured_handler)}),
    )
    out = await client2.generate_structured("sys", "usr")
    assert out == '{"ok": true}'
    assert seen_urls == [
        "http://127.0.0.1:11434/v1/chat/completions",
        "http://host.docker.internal:11434/v1/chat/completions",
        "http://host.docker.internal:11434/v1/chat/completions",
    ]


@pytest.mark.asyncio
async def test_llama_cpp_docker_no_host_server_clear_error(monkeypatch):
    """When inside Docker and both localhost and host.docker.internal fail, report a clear error."""
    monkeypatch.setattr("src.services.llm_client._is_running_in_docker", lambda: True)
    monkeypatch.setattr("src.core.http_client.asyncio.sleep", lambda *_: _noop_coro())
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request):
        raise httpx.ConnectError("All connection attempts failed", request=request)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(*a, **{**kw, "transport": httpx.MockTransport(handler)}),
    )

    client = LlamaCppClient(endpoint_url="http://localhost:8080/v1", model_name="qwen2.5-14b")
    health = await client.test_connection()
    assert health.status == "unreachable"
    assert "http://localhost:8080/v1/chat/completions" in health.message
    assert "http://host.docker.internal:8080/v1/chat/completions" in health.message
    assert "running on the host" in health.message

    with pytest.raises(RuntimeError, match="running on the host"):
        await client.generate_structured("sys", "usr")


@pytest.mark.asyncio
async def test_llama_cpp_no_docker_fallback_outside_container(monkeypatch):
    """Outside Docker, localhost failures should not attempt host.docker.internal."""
    monkeypatch.setattr("src.services.llm_client._is_running_in_docker", lambda: False)
    monkeypatch.setattr("src.core.http_client.asyncio.sleep", lambda *_: _noop_coro())
    seen_hosts: list[str] = []
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request):
        seen_hosts.append(request.url.host)
        raise httpx.ConnectError("Connection refused", request=request)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: real_async_client(*a, **{**kw, "transport": httpx.MockTransport(handler)}),
    )

    client = LlamaCppClient(endpoint_url="http://localhost:8080/v1", model_name="qwen2.5-14b")
    health = await client.test_connection()
    assert health.status == "unreachable"
    assert all(h == "localhost" for h in seen_hosts)


async def _noop_coro() -> None:
    return None
