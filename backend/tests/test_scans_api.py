import pytest

import app.services.onboarding as onboarding


@pytest.fixture(autouse=True)
def no_network_homepage_fetch(monkeypatch):
    async def _fake_fetch_homepage(url: str):
        return {"title": "Acme", "site_name": "Acme", "meta_description": "", "body_text": ""}

    monkeypatch.setattr(onboarding, "fetch_homepage", _fake_fetch_homepage)


async def test_create_scan_returns_202_with_created_status(client):
    response = await client.post("/api/v1/scans", json={"name": "Acme", "website": "acme.com"})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "created"
    assert body["reused"] is False


async def test_duplicate_create_for_active_scan_returns_same_scan_no_new_row(client):
    first = await client.post("/api/v1/scans", json={"name": "Acme", "website": "acme.com"})
    second = await client.post("/api/v1/scans", json={"name": "Acme", "website": "acme.com"})
    assert first.json()["id"] == second.json()["id"]

    listing = await client.get("/api/v1/scans")
    assert len(listing.json()["items"]) == 1


async def test_force_bypasses_reuse_and_creates_a_new_scan(client):
    first = await client.post("/api/v1/scans", json={"name": "Acme", "website": "acme.com"})
    second = await client.post("/api/v1/scans?force=true", json={"name": "Acme", "website": "acme.com"})
    assert first.json()["id"] != second.json()["id"]


async def test_get_scan_returns_status_and_progress(client):
    created = await client.post("/api/v1/scans", json={"name": "Acme", "website": "acme.com"})
    scan_id = created.json()["id"]

    response = await client.get(f"/api/v1/scans/{scan_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "created"
    assert response.json()["progress"] == {}


async def test_get_scan_404_for_unknown_id(client):
    response = await client.get("/api/v1/scans/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_cancel_scan_sets_flag_and_transitions_from_created(client, redis_client):
    created = await client.post("/api/v1/scans", json={"name": "Acme", "website": "acme.com"})
    scan_id = created.json()["id"]

    response = await client.delete(f"/api/v1/scans/{scan_id}")
    assert response.status_code == 204
    assert await redis_client.exists(f"scan:{scan_id}:cancelled")

    fetched = await client.get(f"/api/v1/scans/{scan_id}")
    assert fetched.json()["status"] == "cancelled"
