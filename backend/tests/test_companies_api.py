import pytest

import app.services.onboarding as onboarding


@pytest.fixture(autouse=True)
def no_network_homepage_fetch(monkeypatch):
    """API tests never hit the real internet -- homepage fetch is mocked at
    the boundary, same as every LLM call is mocked through Phase 20."""

    async def _fake_fetch_homepage(url: str):
        return {"title": "Acme", "site_name": "Acme", "meta_description": "", "body_text": ""}

    monkeypatch.setattr(onboarding, "fetch_homepage", _fake_fetch_homepage)


async def test_resolve_creates_and_returns_company(client):
    response = await client.post("/api/v1/companies/resolve", json={"name": "Acme", "website": "acme.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "acme.com"
    assert body["name"] == "Acme"
    assert body["recent_scan_id"] is None


async def test_resolve_rejects_mismatched_company(client, monkeypatch):
    # website must not contain "acme" either, or the domain-evidence escape
    # hatch in check_mismatch forgives a misleading site_name (§7.1 step 5)
    async def _fake_fetch_homepage(url: str):
        return {
            "title": "Globex",
            "site_name": "Totally Different Globex Industries",
            "meta_description": "",
            "body_text": "",
        }

    monkeypatch.setattr(onboarding, "fetch_homepage", _fake_fetch_homepage)

    response = await client.post(
        "/api/v1/companies/resolve", json={"name": "Acme", "website": "globex-industries.io"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "COMPANY_MISMATCH"


async def test_resolve_requires_api_key(client):
    response = await client.post(
        "/api/v1/companies/resolve", json={"name": "Acme", "website": "acme.com"}, headers={"X-API-Key": ""}
    )
    assert response.status_code == 401
