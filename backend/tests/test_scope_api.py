from app.db.repositories.scans import ScanRepository
from app.services.onboarding import upsert_company


async def _make_scan(db_session, *, status="scope_pending"):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status=status)
    await db_session.commit()
    return scan


async def test_set_scope_defaults_to_all_nine_categories_when_omitted(client, db_session):
    scan = await _make_scan(db_session)

    response = await client.put(f"/api/v1/scans/{scan.id}/scope", json={})
    assert response.status_code == 200
    assert len(response.json()["monitoring_categories"]) == 9


async def test_set_scope_stores_the_selected_subset(client, db_session):
    scan = await _make_scan(db_session)

    response = await client.put(
        f"/api/v1/scans/{scan.id}/scope", json={"categories": ["pricing_discussions", "alternatives"]}
    )
    assert response.status_code == 200
    assert response.json()["monitoring_categories"] == ["pricing_discussions", "alternatives"]


async def test_set_scope_rejects_unknown_category(client, db_session):
    scan = await _make_scan(db_session)

    response = await client.put(f"/api/v1/scans/{scan.id}/scope", json={"categories": ["not_a_real_category"]})
    assert response.status_code == 422


async def test_set_scope_rejects_outside_scope_pending(client, db_session):
    scan = await _make_scan(db_session, status="awaiting_verification")

    response = await client.put(f"/api/v1/scans/{scan.id}/scope", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


async def test_set_scope_404_for_unknown_scan(client):
    response = await client.put(
        "/api/v1/scans/00000000-0000-0000-0000-000000000000/scope", json={}
    )
    assert response.status_code == 404
