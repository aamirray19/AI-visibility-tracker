from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.scans import ScanRepository
from app.services.onboarding import upsert_company
from app.worker.settings import InteractiveSettings


async def _make_scan_with_profile(db_session, *, status="awaiting_verification", **profile_fields):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status=status)
    profiles = CompanyProfileRepository(db_session)
    defaults = dict(
        industry="SaaS",
        aliases=["Acme Co"],
        keywords=["productivity"],
        products=[{"name": "Acme Board"}],
        competitors=[{"name": "Globex", "domain": "globex.com"}],
        confidence=0.8,
    )
    defaults.update(profile_fields)
    profile = await profiles.create(scan_id=scan.id, version=1, source="ai_generated", **defaults)
    await db_session.commit()
    return scan, profile


async def test_get_profile_404_when_none_exists(client, db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id)
    await db_session.commit()

    response = await client.get(f"/api/v1/scans/{scan.id}/profile")
    assert response.status_code == 404


async def test_get_profile_returns_latest_version(client, db_session):
    scan, _ = await _make_scan_with_profile(db_session)

    response = await client.get(f"/api/v1/scans/{scan.id}/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["industry"] == "SaaS"


async def test_patch_rejects_when_scan_not_awaiting_verification(client, db_session):
    scan, _ = await _make_scan_with_profile(db_session, status="scope_pending")

    response = await client.patch(f"/api/v1/scans/{scan.id}/profile", json={"industry": "Fintech"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


async def test_patch_creates_v2_and_carries_forward_keywords(client, db_session):
    scan, _ = await _make_scan_with_profile(db_session)

    response = await client.patch(f"/api/v1/scans/{scan.id}/profile", json={"industry": "Fintech"})
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 2
    assert body["source"] == "user_edited"
    assert body["industry"] == "Fintech"
    assert body["keywords"] == ["productivity"]  # not editable, carried forward


async def test_patch_twice_updates_same_v2_row_not_a_new_version(client, db_session):
    scan, _ = await _make_scan_with_profile(db_session)

    await client.patch(f"/api/v1/scans/{scan.id}/profile", json={"industry": "Fintech"})
    response = await client.patch(f"/api/v1/scans/{scan.id}/profile", json={"description": "fintech things"})
    assert response.json()["version"] == 2

    profiles = CompanyProfileRepository(db_session)
    all_versions = await profiles.list(scan_id=scan.id)
    assert len(all_versions) == 2


async def test_patch_does_not_accept_company_or_website_fields(client, db_session):
    scan, _ = await _make_scan_with_profile(db_session)

    response = await client.patch(
        f"/api/v1/scans/{scan.id}/profile", json={"industry": "Fintech", "company": "New Name", "website": "x.com"}
    )
    assert response.status_code == 200  # unknown fields are simply ignored, not applied
    assert response.json()["industry"] == "Fintech"


async def test_confirm_enqueues_verify_profile_when_no_prior_issues(client, db_session, arq_pool):
    scan, _ = await _make_scan_with_profile(db_session)

    response = await client.post(f"/api/v1/scans/{scan.id}/profile/confirm")
    assert response.status_code == 202

    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    assert refreshed.status == "verifying"

    duplicate = await arq_pool.enqueue_job(
        "verify_profile", str(scan.id), _job_id=f"verify:{scan.id}", _queue_name=InteractiveSettings.queue_name
    )
    assert duplicate is None


async def test_confirm_accepts_as_is_when_latest_already_has_issues(client, db_session):
    scan, _ = await _make_scan_with_profile(
        db_session, issues=[{"field": "competitors", "value": "Globex", "reason": "eh"}]
    )

    response = await client.post(f"/api/v1/scans/{scan.id}/profile/confirm")
    assert response.status_code == 202
    body = response.json()
    assert body["source"] == "ai_verified"
    assert body["version"] == 2

    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    assert refreshed.status == "scope_pending"

    entities = ScanEntityRepository(db_session)
    rows = await entities.list(scan_id=scan.id)
    assert len(rows) >= 1
