from app.db.repositories.scans import ScanRepository
from app.services.onboarding import upsert_company
from tests.fixtures.full_scan import seed_full_scan


async def test_dashboard_returns_status_and_metrics(client, db_session):
    scan = await seed_full_scan(db_session)

    response = await client.get(f"/api/v1/scans/{scan.id}/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "summary" in body
    assert body["summary"]["responses_total"] == 8  # 4 categories x 2 providers
    assert body["brand_only"] is False


async def test_dashboard_brand_only_scan(client, db_session):
    scan = await seed_full_scan(db_session, brand_only=True)

    response = await client.get(f"/api/v1/scans/{scan.id}/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["brand_only"] is True
    assert not any(row["name"] == "Globex" for row in body["leaderboard"])


async def test_dashboard_404_when_scan_not_found(client):
    response = await client.get("/api/v1/scans/00000000-0000-0000-0000-000000000000/dashboard")
    assert response.status_code == 404


async def test_dashboard_404_when_metrics_not_yet_computed(client, db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status="executing")
    await db_session.commit()

    response = await client.get(f"/api/v1/scans/{scan.id}/dashboard")
    assert response.status_code == 404
