import pytest

import app.services.onboarding as onboarding
from app.db.repositories.prompts import PromptRepository
from app.db.repositories.responses import AIResponseRepository
from app.db.repositories.scans import ScanRepository
from app.services.onboarding import upsert_company
from app.worker.queues import PIPELINE_QUEUE
from app.worker.settings import InteractiveSettings


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


async def test_create_scan_enqueues_enrich_company(client, arq_pool):
    created = await client.post("/api/v1/scans", json={"name": "Acme", "website": "acme.com"})
    scan_id = created.json()["id"]

    # ARQ refuses a second enqueue under an already-queued job id -- this is
    # a black-box way to prove the first POST actually enqueued the job onto
    # the *interactive* queue specifically (not ARQ's default queue, which a
    # missing `_queue_name` would silently fall back to and the worker would
    # never consume from).
    duplicate = await arq_pool.enqueue_job(
        "enrich_company", scan_id, _job_id=f"enrich:{scan_id}", _queue_name=InteractiveSettings.queue_name
    )
    assert duplicate is None


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
    body = response.json()
    assert body["status"] == "created"
    assert body["progress"] == {}
    assert body["company_name"] == "Acme"
    assert body["company_domain"] == "acme.com"


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


async def test_launch_transitions_to_queued_and_enqueues_generate_prompts(client, db_session, arq_pool):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status="scope_pending")
    await db_session.commit()

    response = await client.post(f"/api/v1/scans/{scan.id}/launch")
    assert response.status_code == 202
    assert response.json()["status"] == "queued"

    duplicate = await arq_pool.enqueue_job(
        "generate_prompts", str(scan.id), _job_id=f"generate_prompts:{scan.id}", _queue_name=PIPELINE_QUEUE
    )
    assert duplicate is None


async def test_launch_rejects_outside_scope_pending(client, db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status="awaiting_verification")
    await db_session.commit()

    response = await client.post(f"/api/v1/scans/{scan.id}/launch")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


async def test_retry_reenqueues_only_failed_and_skipped_responses(client, db_session, arq_pool):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status="failed")
    prompts = PromptRepository(db_session)
    responses = AIResponseRepository(db_session)

    p1 = await prompts.create(scan_id=scan.id, text="p1", category="informational", dedupe_hash="h1")
    p2 = await prompts.create(scan_id=scan.id, text="p2", category="informational", dedupe_hash="h2")
    p3 = await prompts.create(scan_id=scan.id, text="p3", category="informational", dedupe_hash="h3")
    await responses.create(scan_id=scan.id, prompt_id=p1.id, provider="google_ai_studio", model="m", status="failed")
    await responses.create(scan_id=scan.id, prompt_id=p2.id, provider="groq", model="m", status="skipped")
    await responses.create(scan_id=scan.id, prompt_id=p3.id, provider="google_ai_studio", model="m", status="success")
    await db_session.commit()

    response = await client.post(f"/api/v1/scans/{scan.id}/retry")
    assert response.status_code == 202
    assert response.json()["status"] == "executing"

    dup1 = await arq_pool.enqueue_job(
        "execute_prompt", str(scan.id), str(p1.id), "google_ai_studio",
        _job_id=f"exec:{p1.id}:google_ai_studio", _queue_name=PIPELINE_QUEUE,
    )
    dup2 = await arq_pool.enqueue_job(
        "execute_prompt", str(scan.id), str(p2.id), "groq",
        _job_id=f"exec:{p2.id}:groq", _queue_name=PIPELINE_QUEUE,
    )
    assert dup1 is None
    assert dup2 is None

    # the success row must not have been retried
    fresh = await arq_pool.enqueue_job(
        "execute_prompt", str(scan.id), str(p3.id), "google_ai_studio",
        _job_id=f"exec:{p3.id}:google_ai_studio", _queue_name=PIPELINE_QUEUE,
    )
    assert fresh is not None


async def test_retry_rejects_outside_failed_or_completed_with_gaps(client, db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status="executing")
    await db_session.commit()

    response = await client.post(f"/api/v1/scans/{scan.id}/retry")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
