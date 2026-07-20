import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.deps import engine as prod_engine
from app.deps import get_db, get_redis
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def _dispose_prod_engine():
    """health() hits app.deps' module-level engine directly (not the
    per-test db_session fixture), so its pooled asyncpg connections are tied
    to whichever event loop created them. pytest-asyncio hands each test a
    fresh loop, so a connection pooled by an earlier test breaks here --
    dispose after every test to force a fresh pool bound to the next test's
    loop."""
    yield
    await prod_engine.dispose()


async def test_health_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


async def test_health_returns_503_when_redis_down():
    class _BrokenRedis:
        async def ping(self):
            raise ConnectionError("down")

    async def _get_redis():
        return _BrokenRedis()

    app.dependency_overrides[get_redis] = _get_redis
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"] == "error"
    assert body["checks"]["database"] == "ok"


async def test_health_returns_503_when_database_down():
    class _BrokenSession:
        async def execute(self, *args, **kwargs):
            raise ConnectionError("down")

    async def _get_db():
        yield _BrokenSession()

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "error"
