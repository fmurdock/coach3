"""Unit tests for Polar and Concept2 connection verification diagnostics."""

from unittest.mock import patch
import httpx
import pytest

from src.adapters.concept2 import Concept2Adapter
from src.adapters.polar import PolarAdapter


@pytest.mark.asyncio
async def test_polar_verify_healthy():
    def handler(request: httpx.Request):
        assert "Authorization" in request.headers
        return httpx.Response(
            200,
            json={"polar-user-id": 1234567, "member-id": "runner_1"},
            headers={"content-type": "application/json"},
        )

    adapter = PolarAdapter(client_id="test_id", client_secret="test_secret")
    transport = httpx.MockTransport(handler)
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        res = await adapter.verify_connection(access_token="valid_token", user_id="1234567")

    assert res["is_connected"] is True
    assert res["status"] == "healthy"
    assert "1234567" in res["athlete_name"]
    assert res["error"] is None


@pytest.mark.asyncio
async def test_polar_verify_healthy_with_name():
    def handler(request: httpx.Request):
        assert "Authorization" in request.headers
        return httpx.Response(
            200,
            json={
                "polar-user-id": 21417451,
                "first-name": "Frank",
                "last-name": "Murdock",
                "member-id": "runner_1",
            },
            headers={"content-type": "application/json"},
        )

    adapter = PolarAdapter(client_id="test_id", client_secret="test_secret")
    transport = httpx.MockTransport(handler)
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        res = await adapter.verify_connection(access_token="valid_token", user_id="21417451")

    assert res["is_connected"] is True
    assert res["status"] == "healthy"
    assert res["athlete_name"] == "Frank Murdock"
    assert res["error"] is None


@pytest.mark.asyncio
async def test_polar_verify_expired():
    def handler(request: httpx.Request):
        return httpx.Response(401, json={"error": "invalid_token"})

    adapter = PolarAdapter(client_id="test_id", client_secret="test_secret")
    transport = httpx.MockTransport(handler)
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        res = await adapter.verify_connection(access_token="expired_token")

    assert res["is_connected"] is False
    assert res["status"] == "expired"
    assert res["error"] is not None


@pytest.mark.asyncio
async def test_concept2_verify_healthy():
    def handler(request: httpx.Request):
        assert "Authorization" in request.headers
        return httpx.Response(
            200,
            json={"data": {"id": 999, "username": "erg_champ", "first_name": "Erg"}},
            headers={"content-type": "application/json"},
        )

    adapter = Concept2Adapter(client_id="test_id", client_secret="test_secret")
    transport = httpx.MockTransport(handler)
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        res = await adapter.verify_connection(access_token="valid_c2_token")

    assert res["is_connected"] is True
    assert res["status"] == "healthy"
    assert res["athlete_name"] == "erg_champ"
    assert res["error"] is None


@pytest.mark.asyncio
async def test_concept2_verify_expired():
    def handler(request: httpx.Request):
        return httpx.Response(401, json={"error": "unauthorized"})

    adapter = Concept2Adapter(client_id="test_id", client_secret="test_secret")
    transport = httpx.MockTransport(handler)
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        res = await adapter.verify_connection(access_token="expired_c2_token")

    assert res["is_connected"] is False
    assert res["status"] == "expired"
