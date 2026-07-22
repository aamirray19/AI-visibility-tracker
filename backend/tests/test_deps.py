from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.errors import register_error_handlers
from app.deps import require_api_key


def _make_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/probe", dependencies=[Depends(require_api_key)])
    async def probe():
        return {"ok": True}

    return app


async def test_require_api_key_rejects_missing_key():
    transport = ASGITransport(app=_make_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_require_api_key_rejects_wrong_key():
    transport = ASGITransport(app=_make_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


async def test_require_api_key_accepts_correct_key():
    transport = ASGITransport(app=_make_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe", headers={"X-API-Key": settings.api_key})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
