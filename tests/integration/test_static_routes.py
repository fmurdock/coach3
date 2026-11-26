"""Integration tests verifying static routes, shared assets, security headers/CSP, and mobile accessibility."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_all_web_routes_return_200_csp_and_accessible_viewport():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        routes = ["/gym", "/dashboard", "/coach", "/config"]
        for route in routes:
            resp = await client.get(route)
            assert resp.status_code == 200, f"Route {route} failed with status {resp.status_code}"
            text = resp.text

            # Core navigation links
            assert 'href="/gym"' in text, f"Missing /gym link on {route}"
            assert 'href="/dashboard"' in text, f"Missing /dashboard link on {route}"
            assert 'href="/coach"' in text, f"Missing /coach link on {route}"
            assert 'href="/config"' in text, f"Missing /config link on {route}"

            # Shared assets & mobile pinch-to-zoom accessibility
            assert "/static/css/common.css" in text
            assert "/static/js/common.js" in text
            assert "user-scalable=no" not in text
            assert "maximum-scale=1.0" not in text

            # Strict browser security headers / CSP
            csp = resp.headers.get("content-security-policy", "")
            assert "script-src 'self'" in csp
            assert "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
            assert resp.headers.get("x-content-type-options") == "nosniff"
            assert resp.headers.get("x-frame-options") == "DENY"

        # Login route and static assets
        login_resp = await client.get("/login")
        assert login_resp.status_code == 200
        assert "/static/js/login.js" in login_resp.text
        assert "user-scalable=no" not in login_resp.text

        for asset in (
            "/static/css/common.css",
            "/static/js/common.js",
            "/static/js/login.js",
            "/static/js/gym.js",
            "/static/js/config.js",
            "/static/js/dashboard.js",
            "/static/js/coach.js",
        ):
            a_resp = await client.get(asset)
            assert a_resp.status_code == 200, f"Static asset {asset} failed ({a_resp.status_code})"
