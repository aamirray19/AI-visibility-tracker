from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import AppError, register_error_handlers


async def test_app_error_returns_exact_json_shape():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom():
        raise AppError("COMPANY_MISMATCH", "no match", status_code=422, details={"resolved_name": "Acme"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "COMPANY_MISMATCH",
            "message": "no match",
            "details": {"resolved_name": "Acme"},
        }
    }
