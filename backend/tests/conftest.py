import os

import pytest
import pytest_asyncio
import redis.asyncio as redis_asyncio
from arq import create_pool
from arq.connections import RedisSettings
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.deps import get_arq_redis, get_db, get_redis
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://brandmon:brandmon@localhost:5432/brandmon",
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Each test runs inside a transaction that's rolled back afterward,
    so tests never leave rows behind in the dev database."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session_maker = async_sessionmaker(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
        async with session_maker() as session:
            yield session
        await trans.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client():
    client = redis_asyncio.from_url(TEST_REDIS_URL, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def arq_pool(redis_client):
    pool = await create_pool(RedisSettings.from_dsn(TEST_REDIS_URL))
    yield pool
    await pool.aclose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_client, arq_pool):
    """An httpx client against the real app, with get_db/get_redis/get_arq_redis
    pointed at this test's rollback-wrapped session and flushed Redis DB
    instead of the module-level connections app.deps builds from settings."""

    async def _get_db():
        yield db_session

    async def _get_redis():
        return redis_client

    async def _get_arq_redis():
        return arq_pool

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = _get_redis
    app.dependency_overrides[get_arq_redis] = _get_arq_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"X-API-Key": settings.api_key}
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
