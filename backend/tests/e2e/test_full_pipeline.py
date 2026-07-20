"""Phase 21 Task 4: the one test in this suite that spends real LLM tokens.

Walks onboarding -> enrichment -> verification (accepted as-is, skipping the
critique loop -- a real critic call is non-deterministic and could flag
issues forever, which would make this test flaky; "accept as-is" is itself a
legitimate production path, §7.3) -> scope -> launch -> execution ->
evaluation -> aggregation -> dashboard, against real Google AI Studio / Groq
APIs with PROMPT_COUNT turned down for cost.

No real ARQ worker runs during pytest, so each job is invoked directly in
sequence (the same pattern test_jobs.py uses throughout) rather than via
queue consumption -- the enqueue calls inside each job still happen for real
against the `arq_pool` fixture, proving the fan-out wiring, they're just not
auto-consumed here.

Skipped unless real provider keys are present in the environment -- there
are none in local dev by design (plan.md's Global Constraints: every earlier
phase mocks the LLMProvider Protocol; this is the only phase that doesn't).
Run manually: cd backend && pytest tests/e2e/test_full_pipeline.py -v
"""

import pytest
from sqlalchemy import select

from app.config import settings
from app.core.keypool import build_pools
from app.core.lifecycle import transition
from app.db.models import AIResponse, Prompt
from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.metrics import ScanMetricsRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.scans import ScanRepository
from app.llm.google import GoogleAIStudioProvider
from app.llm.groq import GroqProvider
from app.services import verification
from app.services.onboarding import upsert_company
from app.worker import jobs

REAL_KEYS_CONFIGURED = all(
    [
        settings.google_flash_keys,
        settings.google_exec_keys,
        settings.groq_exec_keys,
        settings.groq_eval_a_keys,
        settings.groq_eval_b_keys,
    ]
)

pytestmark = pytest.mark.skipif(
    not REAL_KEYS_CONFIGURED, reason="Phase 21 real-provider smoke test -- needs real key-pool env vars"
)


class _NoCloseSessionCtx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc_info):
        return False


def _build_ctx(db_session, arq_pool, redis_client):
    pools = build_pools(settings)
    return {
        "db_session_factory": lambda: _NoCloseSessionCtx(db_session),
        "redis": arq_pool,
        "providers": {
            "enrichment": GoogleAIStudioProvider(redis_client, pools["google_flash"], settings.model_enrichment),
            "prompt_gen": GoogleAIStudioProvider(redis_client, pools["google_flash"], settings.model_prompt_gen),
            "execution": {
                "google_ai_studio": GoogleAIStudioProvider(redis_client, pools["google_exec"], settings.model_exec_google),
                "groq": GroqProvider(redis_client, pools["groq_exec"], settings.model_exec_groq),
            },
            "evaluation": {
                "eval_a": GroqProvider(redis_client, pools["groq_eval_a"], settings.model_evaluation),
                "eval_b": GroqProvider(redis_client, pools["groq_eval_b"], settings.model_evaluation),
            },
        },
    }


async def test_full_pipeline_against_real_providers(db_session, redis_client, arq_pool, monkeypatch):
    monkeypatch.setattr(settings, "prompt_count", 4)  # real tokens cost money -- keep this small

    ctx = _build_ctx(db_session, arq_pool, redis_client)

    company = await upsert_company(db_session, "Notion", "notion", "notion.so")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id)
    await db_session.commit()
    scan_id = str(scan.id)

    await jobs.enrich_company(ctx, scan_id)

    profiles = CompanyProfileRepository(db_session)
    latest = await profiles.get_latest(scan.id)
    assert latest is not None, "enrich_company should have written a v1 profile"

    await db_session.refresh(scan)
    transition(scan, "verifying")  # confirm_profile does this before accept() in the real API route
    await verification.accept(db_session, scan, company, latest)
    await db_session.commit()
    assert scan.status == "scope_pending"

    entities = ScanEntityRepository(db_session)
    entity_rows = await entities.list(scan_id=scan.id)
    assert any(e.is_target for e in entity_rows), "entity freeze should have written the target entity"

    transition(scan, "queued")  # POST /launch does this before enqueuing generate_prompts
    await db_session.commit()
    await jobs.generate_prompts(ctx, scan_id)
    await db_session.refresh(scan)
    assert scan.status == "executing"

    prompt_rows = (await db_session.execute(select(Prompt).where(Prompt.scan_id == scan.id))).scalars().all()
    assert len(prompt_rows) >= 1

    for prompt in prompt_rows:
        for provider in ("google_ai_studio", "groq"):
            await jobs.execute_prompt(ctx, scan_id, str(prompt.id), provider)

    response_rows = (await db_session.execute(select(AIResponse).where(AIResponse.scan_id == scan.id))).scalars().all()
    for response in response_rows:
        if response.status == "success":
            await jobs.evaluate_response(ctx, str(response.id))

    await jobs.aggregate_scan(ctx, scan_id)
    await jobs.finalize_scan(ctx, scan_id)

    await db_session.refresh(scan)
    assert scan.status in ("completed", "completed_with_gaps"), f"pipeline ended in unexpected status: {scan.status}"

    metrics_repo = ScanMetricsRepository(db_session)
    metrics_row = await metrics_repo.get(scan.id)
    assert metrics_row is not None
    metrics = metrics_row.metrics
    assert "summary" in metrics
    assert "ai_visibility" in metrics["summary"]
    assert 0 <= metrics["summary"]["ai_visibility"] <= 100
