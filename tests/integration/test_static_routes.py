"""Integration tests verifying static routes and unified navigation shell."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_all_web_routes_return_200_and_contain_navigation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        routes = ["/gym", "/dashboard", "/coach", "/config"]
        for route in routes:
            resp = await client.get(route)
            assert resp.status_code == 200, f"Route {route} failed with status {resp.status_code}"
            text = resp.text
            # Check for core navigation links
            assert 'href="/gym"' in text, f"Missing /gym link on {route}"
            assert 'href="/dashboard"' in text, f"Missing /dashboard link on {route}"
            assert 'href="/coach"' in text, f"Missing /coach link on {route}"
            assert 'href="/config"' in text, f"Missing /config link on {route}"
