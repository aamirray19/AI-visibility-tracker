from app.db.repositories.prompts import PromptRepository
from app.db.repositories.responses import AIResponseRepository
from app.db.repositories.scans import ScanRepository
from app.services.onboarding import upsert_company


async def _make_scan_with_responses(db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id)
    prompts = PromptRepository(db_session)
    responses = AIResponseRepository(db_session)

    p1 = await prompts.create(scan_id=scan.id, text="prompt one", category="informational", dedupe_hash="h1")
    p2 = await prompts.create(scan_id=scan.id, text="prompt two", category="commercial", dedupe_hash="h2")
    p3 = await prompts.create(scan_id=scan.id, text="prompt three", category="commercial", dedupe_hash="h3")

    await responses.create(
        scan_id=scan.id,
        prompt_id=p1.id,
        provider="groq",
        model="openai/gpt-oss-120b",
        status="success",
        citations=[{"url": "https://g2.com/a", "domain": "g2.com"}, {"url": "https://reddit.com/b", "domain": "reddit.com"}],
    )
    await responses.create(
        scan_id=scan.id,
        prompt_id=p2.id,
        provider="groq",
        model="openai/gpt-oss-120b",
        status="success",
        citations=[{"url": "https://g2.com/c", "domain": "g2.com"}],
    )
    await responses.create(
        scan_id=scan.id,
        prompt_id=p3.id,
        provider="groq",
        model="openai/gpt-oss-120b",
        status="failed",
        citations=[{"url": "https://ignored.com/d", "domain": "ignored.com"}],
    )
    await db_session.commit()
    return scan


async def test_sources_groups_and_ranks_by_domain(client, db_session):
    scan = await _make_scan_with_responses(db_session)

    response = await client.get(f"/api/v1/scans/{scan.id}/sources")
    assert response.status_code == 200
    sources = response.json()["sources"]

    by_domain = {s["source"]: s["responses"] for s in sources}
    assert by_domain["g2.com"] == 2
    assert by_domain["reddit.com"] == 1
    assert "ignored.com" not in by_domain  # only status='success' counts
    assert sources[0]["source"] == "g2.com"  # ranked highest first


async def test_sources_empty_when_no_citations(client, db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id)
    await db_session.commit()

    response = await client.get(f"/api/v1/scans/{scan.id}/sources")
    assert response.status_code == 200
    assert response.json()["sources"] == []
