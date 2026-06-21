from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_status_timestamp_and_version() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"
    assert body["timestamp"].endswith("Z")
    datetime.fromisoformat(body["timestamp"].replace("Z", "+00:00"))
