"""Test configuration and async fixtures."""

import os
import uuid
from cryptography.fernet import Fernet
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure tests always run in isolated test environment with an ephemeral encryption key
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
os.environ.setdefault("AUTH_DISABLED_LOCALHOST", "true")

from src.models import Base, User, UserHeartRateProfile  # noqa: E402


@pytest.fixture(autouse=True)
def _cleanup_fastapi_overrides():
    """Guarantee FastAPI dependency overrides never leak between tests."""
    from src.main import app

    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession):
    user = User(id=uuid.uuid4())
    db_session.add(user)
    await db_session.flush()

    profile = UserHeartRateProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        resting_hr=48,
        max_hr=190,
        zone1_min=95,
        zone1_max=114,
        zone2_min=114,
        zone2_max=133,
        zone3_min=133,
        zone3_max=152,
        zone4_min=152,
        zone4_max=171,
        zone5_min=171,
        zone5_max=190,
    )
    db_session.add(profile)
    await db_session.commit()
    user.hr_profile = profile
    return user, profile
