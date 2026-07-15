import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_health_needs_no_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_rejects_missing_key():
    from fastapi import APIRouter, Depends
    from app.deps import require_api_key

    router = APIRouter()

    @router.get("/api/v1/_probe", dependencies=[Depends(require_api_key)])
    async def probe():
        return {"ok": True}

    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.get("/api/v1/_probe")
        wrong = await client.get("/api/v1/_probe", headers={"X-API-Key": "wrong"})
        right = await client.get("/api/v1/_probe", headers={"X-API-Key": "dev-local-key"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert right.status_code == 200
