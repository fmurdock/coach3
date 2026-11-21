"""Integration tests for admin demo seed and reset endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.main import app


@pytest.mark.asyncio
async def test_admin_demo_seed_and_reset(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger Seed
        resp_seed = await client.post("/api/v1/admin/demo/seed")
        assert resp_seed.status_code == 201
        data_seed = resp_seed.json()
        assert data_seed["status"] == "success"
        assert data_seed["workouts_created"] == 5

        # 2. Trigger Reset
        resp_reset = await client.delete("/api/v1/admin/demo")
        assert resp_reset.status_code == 200
        data_reset = resp_reset.json()
        assert data_reset["status"] == "success"
        assert data_reset["workouts_deleted"] == 5

    app.dependency_overrides.pop(get_db, None)
