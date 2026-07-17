import os

import pytest
import pytest_asyncio
import redis.asyncio as redis_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
