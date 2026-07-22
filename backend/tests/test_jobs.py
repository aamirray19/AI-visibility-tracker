import json

import pytest
from sqlalchemy import select, text

from app.api.v1.scans import MonitoringCategory
from app.config import settings
from app.core.keypool import PoolExhausted
from app.core.locks import try_acquire_advance_lock
from app.db.models import ScanMetrics
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.evaluations import EvaluationRepository
from app.db.repositories.mentions import MentionRepository
from app.db.repositories.metrics import ScanMetricsRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.prompts import PromptRepository
from app.db.repositories.responses import AIResponseRepository
from app.db.repositories.scans import ScanRepository
from app.llm.base import LLMResponse
from app.services import verification
from app.services.onboarding import upsert_company
from app.worker import jobs
from tests.test_enrichment import KNOWN_COMPANY, FakeProvider
from tests.test_prompt_gen import FakePromptProvider


class _NoCloseSessionCtx:
    """Wraps the test's rollback-scoped db_session so `enrich_company`'s
    `async with session_factory() as session:` doesn't close it out from
    under the test -- db_session's own fixture owns open/rollback."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc_info):
        return False


class FailingProvider:
    model = "gemini-2.5-flash"

    async def complete(self, *args, **kwargs):
        raise RuntimeError("boom")


def _make_ctx(db_session, redis_client, **providers):
    return {
        "db_session_factory": lambda: _NoCloseSessionCtx(db_session),
        "redis": redis_client,
        "providers": providers,
    }


async def _make_scan(db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id)
    await db_session.commit()
    return scan


async def _make_scan_scope_pending(db_session, redis_client, *, with_competitors=True):
    """Runs the real enrich -> patch -> accept flow so scan_entities are
    genuinely frozen the way generate_prompts expects, landing at
    scope_pending with scope set to all 9 categories."""
    scan = await _make_scan(db_session)
    ctx = _make_ctx(db_session, redis_client, enrichment=FakeProvider(KNOWN_COMPANY))
    await jobs.enrich_company(ctx, str(scan.id))

    scans = ScanRepository(db_session)
    profiles = CompanyProfileRepository(db_session)
    companies = CompanyRepository(db_session)

    scan = await scans.get(scan.id)
    v1 = await profiles.get_latest(scan.id)
    if not with_competitors:
        v1.competitors = []
        await db_session.flush()
    scan.status = "verifying"
    await db_session.commit()

    company = await companies.get(scan.company_id)
    await verification.accept(db_session, scan, company, v1)
    scan.monitoring_categories = [c.value for c in MonitoringCategory]
    await db_session.commit()
    return scan


async def test_enrich_company_writes_profile_v1_and_transitions_to_awaiting_verification(db_session, redis_client):
    scan = await _make_scan(db_session)
    ctx = _make_ctx(db_session, redis_client, enrichment=FakeProvider(KNOWN_COMPANY))

    await jobs.enrich_company(ctx, str(scan.id))

    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    assert refreshed.status == "awaiting_verification"

    profiles = CompanyProfileRepository(db_session)
    rows = await profiles.list(scan_id=scan.id)
    assert len(rows) == 1
    assert rows[0].version == 1
    assert rows[0].source == "ai_generated"
    assert rows[0].industry == "SaaS"


async def test_enrich_company_publishes_progress(db_session, redis_client):
    scan = await _make_scan(db_session)
    ctx = _make_ctx(db_session, redis_client, enrichment=FakeProvider(KNOWN_COMPANY))

    await jobs.enrich_company(ctx, str(scan.id))

    progress = await redis_client.hgetall(f"scan:{scan.id}:progress")
    assert progress["stage"] == "awaiting_verification"


async def test_enrich_company_marks_scan_failed_on_llm_error(db_session, redis_client):
    scan = await _make_scan(db_session)
    ctx = _make_ctx(db_session, redis_client, enrichment=FailingProvider())

    with pytest.raises(RuntimeError):
        await jobs.enrich_company(ctx, str(scan.id))

    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    assert refreshed.status == "failed"
    assert refreshed.error_code == "SCAN_FAILED"

    profiles = CompanyProfileRepository(db_session)
    assert await profiles.list(scan_id=scan.id) == []


async def test_verify_profile_issues_found_stays_at_awaiting_verification(db_session, redis_client):
    scan = await _make_scan(db_session)
    ctx = _make_ctx(db_session, redis_client, enrichment=FakeProvider(KNOWN_COMPANY))
    await jobs.enrich_company(ctx, str(scan.id))

    profiles = CompanyProfileRepository(db_session)
    v1 = await profiles.get_latest(scan.id)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    v2 = await verification.apply_patch(db_session, scan, v1, {"industry": "Fintech"})
    await db_session.commit()

    critic_response = FakeProvider(
        {
            "verdict": "issues_found",
            "issues": [{"field": "competitors", "value": "Globex", "reason": "not a real competitor"}],
        }
    )
    ctx = _make_ctx(db_session, redis_client, verification=critic_response)
    scan.status = "verifying"
    await db_session.commit()

    await jobs.verify_profile(ctx, str(scan.id))

    refreshed = await scans.get(scan.id)
    assert refreshed.status == "awaiting_verification"

    v2_after = await profiles.get_latest(scan.id)
    assert v2_after.version == v2.version
    assert v2_after.issues == [{"field": "competitors", "value": "Globex", "reason": "not a real competitor"}]

    entities = ScanEntityRepository(db_session)
    assert await entities.list(scan_id=scan.id) == []  # not frozen yet


async def test_verify_profile_ok_writes_v3_and_freezes_entities(db_session, redis_client):
    scan = await _make_scan(db_session)
    ctx = _make_ctx(db_session, redis_client, enrichment=FakeProvider(KNOWN_COMPANY))
    await jobs.enrich_company(ctx, str(scan.id))

    profiles = CompanyProfileRepository(db_session)
    v1 = await profiles.get_latest(scan.id)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    await verification.apply_patch(db_session, scan, v1, {"industry": "Fintech"})
    await db_session.commit()

    ctx = _make_ctx(db_session, redis_client, verification=FakeProvider({"verdict": "ok", "issues": []}))
    scan.status = "verifying"
    await db_session.commit()

    await jobs.verify_profile(ctx, str(scan.id))

    refreshed = await scans.get(scan.id)
    assert refreshed.status == "scope_pending"

    v3 = await profiles.get_latest(scan.id)
    assert v3.source == "ai_verified"

    entities = ScanEntityRepository(db_session)
    rows = await entities.list(scan_id=scan.id)
    assert any(e.is_target for e in rows)


async def test_verify_profile_marks_scan_failed_on_llm_error(db_session, redis_client):
    scan = await _make_scan(db_session)
    ctx = _make_ctx(db_session, redis_client, enrichment=FakeProvider(KNOWN_COMPANY))
    await jobs.enrich_company(ctx, str(scan.id))

    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "verifying"
    await db_session.commit()

    ctx = _make_ctx(db_session, redis_client, verification=FailingProvider())
    with pytest.raises(RuntimeError):
        await jobs.verify_profile(ctx, str(scan.id))

    refreshed = await scans.get(scan.id)
    assert refreshed.status == "failed"
    assert refreshed.error_code == "SCAN_FAILED"


async def test_full_verification_flow_issues_then_accept(db_session, redis_client):
    """Walks the whole state machine per the Phase 5 testing checkpoint:
    awaiting_verification -> (PATCH) -> confirm -> verifying ->
    (issues_found) -> awaiting_verification -> (confirm again) ->
    scope_pending."""
    scan = await _make_scan(db_session)
    scans = ScanRepository(db_session)
    profiles = CompanyProfileRepository(db_session)

    ctx = _make_ctx(db_session, redis_client, enrichment=FakeProvider(KNOWN_COMPANY))
    await jobs.enrich_company(ctx, str(scan.id))
    scan = await scans.get(scan.id)
    assert scan.status == "awaiting_verification"

    v1 = await profiles.get_latest(scan.id)
    v2 = await verification.apply_patch(db_session, scan, v1, {"industry": "Fintech"})
    await db_session.commit()
    assert v2.source == "user_edited"

    # first confirm -> verifying -> critic finds issues -> back to awaiting_verification
    scan.status = "verifying"
    await db_session.commit()
    ctx = _make_ctx(
        db_session,
        redis_client,
        verification=FakeProvider(
            {"verdict": "issues_found", "issues": [{"field": "competitors", "value": "Globex", "reason": "eh"}]}
        ),
    )
    await jobs.verify_profile(ctx, str(scan.id))
    scan = await scans.get(scan.id)
    assert scan.status == "awaiting_verification"
    v2_with_issues = await profiles.get_latest(scan.id)
    assert v2_with_issues.issues

    # second confirm -- API's confirm_profile would call accept() directly
    # here since latest.issues is non-empty, skipping the critic entirely
    scan.status = "verifying"
    await db_session.commit()
    companies = CompanyRepository(db_session)
    company = await companies.get(scan.company_id)
    await verification.accept(db_session, scan, company, v2_with_issues)
    await db_session.commit()

    scan = await scans.get(scan.id)
    assert scan.status == "scope_pending"

    v3 = await profiles.get_latest(scan.id)
    assert v3.source == "ai_verified"
    all_versions = await profiles.list(scan_id=scan.id)
    assert sorted(v.version for v in all_versions) == [1, 2, 3]  # Repository.list() has no ORDER BY

    entities = ScanEntityRepository(db_session)
    rows = await entities.list(scan_id=scan.id)
    assert any(e.is_target for e in rows)
    assert any(not e.is_target for e in rows)


async def test_generate_prompts_writes_prompts_and_fans_out_execution(db_session, redis_client, arq_pool, monkeypatch):
    # Pinned rather than relying on the ambient .env's PROMPT_COUNT -- a
    # developer's local override (e.g. for a cheap real-provider smoke test)
    # must not change what this test asserts.
    monkeypatch.setattr(settings, "prompt_count", 50)
    scan = await _make_scan_scope_pending(db_session, redis_client)
    scan.status = "queued"
    await db_session.commit()

    ctx = _make_ctx(db_session, arq_pool, prompt_gen=FakePromptProvider())
    await jobs.generate_prompts(ctx, str(scan.id))

    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    assert refreshed.status == "executing"
    assert refreshed.brand_only is False

    prompts = PromptRepository(db_session)
    rows = await prompts.list(scan_id=scan.id)
    assert 30 <= len(rows) <= 50

    pending_exec = await redis_client.get(f"scan:{scan.id}:pending_exec")
    pending_eval = await redis_client.get(f"scan:{scan.id}:pending_eval")
    assert int(pending_exec) == len(rows) * 2
    assert int(pending_eval) == len(rows) * 2

    # execute_prompt jobs were enqueued (not executed) -- verified the same
    # way Phase 4's enqueue test was: a duplicate enqueue under the same
    # deterministic job id is refused.
    sample_prompt = rows[0]
    duplicate = await arq_pool.enqueue_job(
        "execute_prompt",
        str(scan.id),
        str(sample_prompt.id),
        "google_ai_studio",
        _job_id=f"exec:{sample_prompt.id}:google_ai_studio",
        _queue_name="arq:pipeline",
    )
    assert duplicate is None


async def test_generate_prompts_brand_only_when_no_competitors(db_session, redis_client, arq_pool):
    scan = await _make_scan_scope_pending(db_session, redis_client, with_competitors=False)
    scan.status = "queued"
    await db_session.commit()

    ctx = _make_ctx(db_session, arq_pool, prompt_gen=FakePromptProvider())
    await jobs.generate_prompts(ctx, str(scan.id))

    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    assert refreshed.brand_only is True

    prompts = PromptRepository(db_session)
    rows = await prompts.list(scan_id=scan.id)
    assert not any(p.category == "competitor_discovery" for p in rows)


async def test_generate_prompts_marks_scan_failed_on_llm_error(db_session, redis_client, arq_pool):
    scan = await _make_scan_scope_pending(db_session, redis_client)
    scan.status = "queued"
    await db_session.commit()

    ctx = _make_ctx(db_session, arq_pool, prompt_gen=FailingProvider())
    with pytest.raises(RuntimeError):
        await jobs.generate_prompts(ctx, str(scan.id))

    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    assert refreshed.status == "failed"
    assert refreshed.error_code == "SCAN_FAILED"


class FakeExecProvider:
    model = "gemma-4-31b-it"

    def __init__(self, response=None, raises=None):
        self._response = response
        self._raises = raises

    async def complete(self, prompt, *, tools=None, timeout=60.0, **kwargs):
        if self._raises:
            raise self._raises
        return self._response


def _exec_response(**overrides):
    fields = dict(
        text="the answer", latency_ms=10, model="gemma-4-31b-it", tokens_in=5, tokens_out=5, key_id="k1"
    )
    fields.update(overrides)
    return LLMResponse(**fields)


async def _make_prompt(db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id)
    prompts = PromptRepository(db_session)
    prompt = await prompts.create(
        scan_id=scan.id, text="What are good tools for this", category="informational", dedupe_hash="h1"
    )
    await db_session.commit()
    return scan, prompt


def _exec_ctx(db_session, arq_pool, provider):
    return {
        "db_session_factory": lambda: _NoCloseSessionCtx(db_session),
        "redis": arq_pool,
        "providers": {"execution": {"google_ai_studio": provider}},
    }


async def test_execute_prompt_success_upserts_response_and_enqueues_evaluation(db_session, arq_pool):
    scan, prompt = await _make_prompt(db_session)
    await arq_pool.set(f"scan:{scan.id}:pending_exec", 1)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 1)

    provider = FakeExecProvider(response=_exec_response())
    ctx = _exec_ctx(db_session, arq_pool, provider)
    await jobs.execute_prompt(ctx, str(scan.id), str(prompt.id), "google_ai_studio")

    responses = AIResponseRepository(db_session)
    rows = await responses.list(prompt_id=prompt.id)
    assert len(rows) == 1
    assert rows[0].status == "success"

    assert int(await arq_pool.get(f"scan:{scan.id}:pending_exec")) == 0
    assert int(await arq_pool.get(f"scan:{scan.id}:pending_eval")) == 1  # untouched on success

    duplicate = await arq_pool.enqueue_job(
        "evaluate_response", str(rows[0].id), _job_id=f"eval:{rows[0].id}", _queue_name="arq:pipeline"
    )
    assert duplicate is None  # already enqueued by execute_prompt


async def test_execute_prompt_failure_decrements_both_counters_and_skips_evaluation(db_session, arq_pool):
    scan, prompt = await _make_prompt(db_session)
    await arq_pool.set(f"scan:{scan.id}:pending_exec", 1)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 1)

    provider = FakeExecProvider(raises=RuntimeError("boom"))
    ctx = _exec_ctx(db_session, arq_pool, provider)
    await jobs.execute_prompt(ctx, str(scan.id), str(prompt.id), "google_ai_studio")

    responses = AIResponseRepository(db_session)
    rows = await responses.list(prompt_id=prompt.id)
    assert rows[0].status == "failed"

    assert int(await arq_pool.get(f"scan:{scan.id}:pending_exec")) == 0
    assert int(await arq_pool.get(f"scan:{scan.id}:pending_eval")) == 0

    # not enqueued -- nothing to evaluate
    job = await arq_pool.enqueue_job(
        "evaluate_response", str(rows[0].id), _job_id=f"eval:{rows[0].id}", _queue_name="arq:pipeline"
    )
    assert job is not None


async def test_execute_prompt_pool_exhausted_writes_skipped_status(db_session, arq_pool):
    scan, prompt = await _make_prompt(db_session)
    await arq_pool.set(f"scan:{scan.id}:pending_exec", 1)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 1)

    provider = FakeExecProvider(raises=PoolExhausted("google_exec"))
    ctx = _exec_ctx(db_session, arq_pool, provider)
    await jobs.execute_prompt(ctx, str(scan.id), str(prompt.id), "google_ai_studio")

    responses = AIResponseRepository(db_session)
    rows = await responses.list(prompt_id=prompt.id)
    assert rows[0].status == "skipped"


async def test_execute_prompt_idempotent_upsert_on_retry(db_session, arq_pool):
    scan, prompt = await _make_prompt(db_session)
    await arq_pool.set(f"scan:{scan.id}:pending_exec", 2)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 2)

    provider = FakeExecProvider(response=_exec_response())
    ctx = _exec_ctx(db_session, arq_pool, provider)
    await jobs.execute_prompt(ctx, str(scan.id), str(prompt.id), "google_ai_studio")
    await jobs.execute_prompt(ctx, str(scan.id), str(prompt.id), "google_ai_studio")

    responses = AIResponseRepository(db_session)
    rows = await responses.list(prompt_id=prompt.id)
    assert len(rows) == 1
    assert rows[0].attempts == 2


async def test_execute_prompt_bails_early_when_cancelled(db_session, arq_pool):
    scan, prompt = await _make_prompt(db_session)
    await arq_pool.set(f"scan:{scan.id}:cancelled", "1")
    await arq_pool.set(f"scan:{scan.id}:pending_exec", 1)

    provider = FakeExecProvider(response=_exec_response())
    ctx = _exec_ctx(db_session, arq_pool, provider)
    await jobs.execute_prompt(ctx, str(scan.id), str(prompt.id), "google_ai_studio")

    responses = AIResponseRepository(db_session)
    assert await responses.list(prompt_id=prompt.id) == []
    assert int(await arq_pool.get(f"scan:{scan.id}:pending_exec")) == 1  # untouched


GOOD_EVAL_JSON = json.dumps(
    {
        "sentiment": "positive",
        "recommended": True,
        "rank_position": 1,
        "mentioned_companies": ["Acme", "Globex", "Initech"],
        "confidence": 0.9,
        "reasoning": "Acme is recommended first.",
    }
)


class FakeEvalProvider:
    model = "llama-3.3-70b-versatile"

    def __init__(self, text=GOOD_EVAL_JSON, raises=None):
        self._text = text
        self._raises = raises
        self.calls = 0

    async def complete(self, prompt, *, schema=None, timeout=60.0, **kwargs):
        self.calls += 1
        if self._raises:
            raise self._raises
        return LLMResponse(text=self._text, latency_ms=10, model=self.model)


async def _make_ai_response(db_session, *, raw_response="I'd recommend Acme, then Globex."):
    scan, prompt = await _make_prompt(db_session)
    entities = ScanEntityRepository(db_session)
    target = await entities.create(
        scan_id=scan.id, name="Acme", name_norm="acme", is_target=True, aliases=[]
    )
    competitor = await entities.create(
        scan_id=scan.id, name="Globex", name_norm="globex", is_target=False, aliases=[]
    )
    responses = AIResponseRepository(db_session)
    response = await responses.upsert(
        scan_id=scan.id,
        prompt_id=prompt.id,
        provider="google_ai_studio",
        model="gemma-4-31b-it",
        status="success",
        raw_response=raw_response,
        citations=[],
    )
    await db_session.commit()
    return scan, response, target, competitor


def _eval_ctx(db_session, arq_pool, provider):
    return {
        "db_session_factory": lambda: _NoCloseSessionCtx(db_session),
        "redis": arq_pool,
        "providers": {"evaluation": {"eval_a": provider, "eval_b": provider}},
    }


async def test_evaluate_response_writes_evaluation_and_fans_out_mentions(db_session, arq_pool):
    scan, response, target, competitor = await _make_ai_response(db_session)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 2)

    ctx = _eval_ctx(db_session, arq_pool, FakeEvalProvider())
    await jobs.evaluate_response(ctx, str(response.id))

    evaluations = EvaluationRepository(db_session)
    ev = await evaluations.get_by_response(response.id)
    assert ev.target_mentioned is True
    assert ev.sentiment == "positive"
    assert ev.rank_position == 1
    assert ev.evaluator_pool == "eval_a"

    mentions = MentionRepository(db_session)
    rows = await mentions.list(scan_id=scan.id)
    by_name = {m.raw_name: m for m in rows}
    assert by_name["Acme"].is_target is True
    assert by_name["Acme"].entity_id == target.id
    assert by_name["Globex"].entity_id == competitor.id
    assert by_name["Initech"].entity_id is None  # discovered company

    assert int(await arq_pool.get(f"scan:{scan.id}:pending_eval")) == 1


async def test_evaluate_response_target_not_mentioned_short_circuits_stage_b_fields(db_session, arq_pool):
    scan, response, target, competitor = await _make_ai_response(db_session, raw_response="Try Globex instead.")
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 1)

    ctx = _eval_ctx(db_session, arq_pool, FakeEvalProvider())  # LLM still says positive/recommended/rank=1
    await jobs.evaluate_response(ctx, str(response.id))

    evaluations = EvaluationRepository(db_session)
    ev = await evaluations.get_by_response(response.id)
    assert ev.target_mentioned is False
    assert ev.sentiment is None  # Stage A authoritative: not mentioned means no sentiment recorded
    assert ev.recommended is False
    assert ev.rank_position is None


async def test_evaluate_response_is_idempotent_on_rerun(db_session, arq_pool):
    scan, response, target, competitor = await _make_ai_response(db_session)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 2)

    ctx = _eval_ctx(db_session, arq_pool, FakeEvalProvider())
    await jobs.evaluate_response(ctx, str(response.id))
    await jobs.evaluate_response(ctx, str(response.id))  # stray duplicate run

    evaluations = EvaluationRepository(db_session)
    all_evals = await evaluations.list(response_id=response.id)
    assert len(all_evals) == 1


async def test_evaluate_response_pool_exhausted_defers_instead_of_skipping(db_session, arq_pool):
    scan, response, target, competitor = await _make_ai_response(db_session)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 1)

    ctx = _eval_ctx(db_session, arq_pool, FakeEvalProvider(raises=PoolExhausted("groq_eval_a")))
    await jobs.evaluate_response(ctx, str(response.id))

    evaluations = EvaluationRepository(db_session)
    assert await evaluations.get_by_response(response.id) is None
    # pending_eval untouched -- deferred, not skipped (§13.3)
    assert int(await arq_pool.get(f"scan:{scan.id}:pending_eval")) == 1


async def test_evaluate_response_pending_eval_zero_enqueues_aggregate_scan(db_session, arq_pool):
    scan, response, target, competitor = await _make_ai_response(db_session)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 1)

    ctx = _eval_ctx(db_session, arq_pool, FakeEvalProvider())
    await jobs.evaluate_response(ctx, str(response.id))

    duplicate = await arq_pool.enqueue_job(
        "aggregate_scan", str(scan.id), _job_id=f"agg:{scan.id}", _queue_name="arq:pipeline"
    )
    assert duplicate is None


async def test_execute_prompt_last_one_transitions_scan_to_evaluating(db_session, arq_pool):
    scan, prompt = await _make_prompt(db_session)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "executing"
    await db_session.commit()
    await arq_pool.set(f"scan:{scan.id}:pending_exec", 1)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 1)

    provider = FakeExecProvider(response=_exec_response())
    ctx = _exec_ctx(db_session, arq_pool, provider)
    await jobs.execute_prompt(ctx, str(scan.id), str(prompt.id), "google_ai_studio")

    refreshed = await scans.get(scan.id)
    assert refreshed.status == "evaluating"


async def _make_scan_ready_to_aggregate(db_session, *, n_total=2, n_evaluated=2):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status="evaluating", brand_only=False)
    entities = ScanEntityRepository(db_session)
    await entities.create(scan_id=scan.id, name="Acme", name_norm="acme", is_target=True, aliases=[])

    prompts = PromptRepository(db_session)
    responses = AIResponseRepository(db_session)
    evaluations = EvaluationRepository(db_session)

    for i in range(n_total):
        prompt = await prompts.create(scan_id=scan.id, text=f"prompt {i}", category="informational", dedupe_hash=f"h{i}")
        response = await responses.create(
            scan_id=scan.id, prompt_id=prompt.id, provider="google_ai_studio", model="m", status="success"
        )
        if i < n_evaluated:
            await evaluations.create(scan_id=scan.id, response_id=response.id, target_mentioned=True, recommended=True)

    await db_session.commit()
    return scan


def _agg_ctx(db_session, arq_pool):
    return {
        "db_session_factory": lambda: _NoCloseSessionCtx(db_session),
        "redis": arq_pool,
        "providers": {},
    }


async def test_aggregate_scan_defers_when_evaluated_less_than_total(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=2, n_evaluated=1)
    ctx = _agg_ctx(db_session, arq_pool)

    await jobs.aggregate_scan(ctx, str(scan.id))

    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    assert refreshed.status == "evaluating"  # unchanged -- woken too early, went back to sleep

    assert await ScanMetricsRepository(db_session).get(scan.id) is None


async def test_aggregate_scan_computes_metrics_and_enqueues_finalize(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=2, n_evaluated=2)
    ctx = _agg_ctx(db_session, arq_pool)

    await jobs.aggregate_scan(ctx, str(scan.id))

    row = await ScanMetricsRepository(db_session).get(scan.id)
    assert row is not None
    assert row.metrics["summary"]["responses_total"] == 2
    assert row.metrics["brand_only"] is False

    duplicate = await arq_pool.enqueue_job(
        "finalize_scan", str(scan.id), _job_id=f"finalize:{scan.id}", _queue_name="arq:pipeline"
    )
    assert duplicate is None


async def test_aggregate_scan_upsert_is_idempotent_on_double_fire(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=2, n_evaluated=2)
    ctx = _agg_ctx(db_session, arq_pool)

    await jobs.aggregate_scan(ctx, str(scan.id))
    scans = ScanRepository(db_session)
    refreshed = await scans.get(scan.id)
    refreshed.status = "evaluating"  # simulate a second wakeup being possible
    await db_session.commit()
    await jobs.aggregate_scan(ctx, str(scan.id))

    all_rows = await db_session.execute(select(ScanMetrics).where(ScanMetrics.scan_id == scan.id))
    assert len(list(all_rows.scalars().all())) == 1


async def test_finalize_scan_completed_sets_finished_at_and_writes_recent_cache(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=2, n_evaluated=2)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "aggregating"
    await db_session.commit()

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.finalize_scan(ctx, str(scan.id))

    refreshed = await scans.get(scan.id)
    assert refreshed.status == "completed"
    assert refreshed.finished_at is not None
    cached = await arq_pool.get("scan:recent:acme.com")
    assert cached.decode() == str(scan.id)  # arq_pool has no decode_responses=True, unlike redis_client


async def test_finalize_scan_failed_does_not_write_recent_cache(db_session, arq_pool):
    company = await upsert_company(db_session, "Acme", "acme", "acme-failed.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status="aggregating")
    prompts = PromptRepository(db_session)
    responses = AIResponseRepository(db_session)
    prompt = await prompts.create(scan_id=scan.id, text="p", category="informational", dedupe_hash="hx")
    await responses.create(scan_id=scan.id, prompt_id=prompt.id, provider="google_ai_studio", model="m", status="failed")
    await db_session.commit()

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.finalize_scan(ctx, str(scan.id))

    refreshed = await scans.get(scan.id)
    assert refreshed.status == "failed"
    assert await arq_pool.get("scan:recent:acme-failed.com") is None


async def test_finalize_scan_clears_progress_cache(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=2, n_evaluated=2)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "aggregating"
    await db_session.commit()
    await arq_pool.hset(f"scan:{scan.id}:progress", mapping={"stage": "aggregating", "done": "0", "total": "0"})

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.finalize_scan(ctx, str(scan.id))

    assert not await arq_pool.exists(f"scan:{scan.id}:progress")


async def test_execute_prompt_cost_ceiling_exceeded_marks_scan_failed(db_session, arq_pool):
    scan, prompt = await _make_prompt(db_session)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "executing"
    await db_session.commit()
    await arq_pool.set(f"scan:{scan.id}:pending_exec", 1)
    await arq_pool.set(f"scan:{scan.id}:pending_eval", 1)

    provider = FakeExecProvider(response=_exec_response(cost_usd=settings.scan_cost_ceiling_usd + 1))
    ctx = _exec_ctx(db_session, arq_pool, provider)
    await jobs.execute_prompt(ctx, str(scan.id), str(prompt.id), "google_ai_studio")

    refreshed = await scans.get(scan.id)
    assert refreshed.status == "failed"
    assert refreshed.error_code == "COST_CEILING_EXCEEDED"
    assert await arq_pool.exists(f"scan:{scan.id}:cancelled")

    responses = AIResponseRepository(db_session)
    rows = await responses.list(prompt_id=prompt.id)
    # the response row is still written (it already cost money) but no
    # evaluation was enqueued for it
    assert len(rows) == 1
    not_enqueued = await arq_pool.enqueue_job(
        "evaluate_response", str(rows[0].id), _job_id=f"eval:{rows[0].id}", _queue_name="arq:pipeline"
    )
    assert not_enqueued is not None


async def test_evaluate_response_bails_when_cancelled(db_session, arq_pool):
    scan, response, target, competitor = await _make_ai_response(db_session)
    await arq_pool.set(f"scan:{scan.id}:cancelled", "1")

    ctx = _eval_ctx(db_session, arq_pool, FakeEvalProvider())
    await jobs.evaluate_response(ctx, str(response.id))

    evaluations = EvaluationRepository(db_session)
    assert await evaluations.get_by_response(response.id) is None


async def test_aggregate_scan_cancelled_skips_defer_guard(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=2, n_evaluated=1)
    await arq_pool.set(f"scan:{scan.id}:cancelled", "1")
    ctx = _agg_ctx(db_session, arq_pool)

    await jobs.aggregate_scan(ctx, str(scan.id))

    row = await ScanMetricsRepository(db_session).get(scan.id)
    assert row is not None  # proceeded despite evaluated < total


async def test_aggregate_scan_from_executing_status_transitions_through_evaluating(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=1, n_evaluated=1)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "executing"
    await db_session.commit()

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.aggregate_scan(ctx, str(scan.id))

    refreshed = await scans.get(scan.id)
    assert refreshed.status == "aggregating"


# --- sweeper / reconcile (§13.4) --------------------------------------------


async def test_reconcile_executing_reenqueues_missing_execute_prompt_jobs(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=1, n_evaluated=1)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "executing"
    prompts = PromptRepository(db_session)
    # a second prompt that never got an ai_responses row at all
    missing_prompt = await prompts.create(scan_id=scan.id, text="missing", category="informational", dedupe_hash="hmissing")
    await db_session.commit()

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.reconcile(ctx, str(scan.id), "executing")

    dup = await arq_pool.enqueue_job(
        "execute_prompt", str(scan.id), str(missing_prompt.id), "google_ai_studio",
        _job_id=f"exec:{missing_prompt.id}:google_ai_studio", _queue_name="arq:pipeline",
    )
    assert dup is None  # reconcile already enqueued it


async def test_reconcile_evaluating_reenqueues_missing_evaluate_response_jobs(db_session, arq_pool):
    scan, response, target, competitor = await _make_ai_response(db_session)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "evaluating"
    await db_session.commit()

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.reconcile(ctx, str(scan.id), "evaluating")

    dup = await arq_pool.enqueue_job(
        "evaluate_response", str(response.id), _job_id=f"eval:{response.id}", _queue_name="arq:pipeline"
    )
    assert dup is None


async def test_reconcile_nothing_missing_enqueues_aggregate_scan(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=1, n_evaluated=1)

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.reconcile(ctx, str(scan.id), "evaluating")

    dup = await arq_pool.enqueue_job(
        "aggregate_scan", str(scan.id), _job_id=f"agg:{scan.id}:sweep", _queue_name="arq:pipeline"
    )
    assert dup is None  # reconcile already enqueued it under this exact id
    assert await ScanMetricsRepository(db_session).get(scan.id) is None  # not run yet, just enqueued


async def test_reconcile_cancelled_scan_skips_missing_work_and_pushes_forward(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=2, n_evaluated=1)
    scans = ScanRepository(db_session)
    scan = await scans.get(scan.id)
    scan.status = "evaluating"
    await db_session.commit()
    await arq_pool.set(f"scan:{scan.id}:cancelled", "1")

    prompts = PromptRepository(db_session)
    responses = AIResponseRepository(db_session)
    rows = []
    for p in await prompts.list(scan_id=scan.id):
        rows.extend(await responses.list(prompt_id=p.id))
    unevaluated = [r for r in rows if r.status == "success"][-1]  # the one without an evaluation

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.reconcile(ctx, str(scan.id), "evaluating")

    # a cancelled scan must NOT get its missing evaluation re-enqueued
    would_be_new = await arq_pool.enqueue_job(
        "evaluate_response", str(unevaluated.id), _job_id=f"eval:{unevaluated.id}", _queue_name="arq:pipeline"
    )
    assert would_be_new is not None  # proves reconcile did NOT already enqueue it


async def test_reconcile_respects_advance_lock(db_session, arq_pool):
    scan = await _make_scan_ready_to_aggregate(db_session, n_total=1, n_evaluated=0)
    await try_acquire_advance_lock(arq_pool, str(scan.id))

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.reconcile(ctx, str(scan.id), "evaluating")  # should no-op, lock held

    # nothing enqueued -- a fresh enqueue attempt for the missing eval succeeds (proves reconcile skipped it)
    prompts = PromptRepository(db_session)
    responses = AIResponseRepository(db_session)
    rows = []
    for p in await prompts.list(scan_id=scan.id):
        rows.extend(await responses.list(prompt_id=p.id))
    job = await arq_pool.enqueue_job(
        "evaluate_response", str(rows[0].id), _job_id=f"eval:{rows[0].id}", _queue_name="arq:pipeline"
    )
    assert job is not None


async def test_sweep_stalled_scans_reconciles_only_old_stalled_scans(db_session, arq_pool):
    stale = await _make_scan_ready_to_aggregate(db_session, n_total=1, n_evaluated=1)
    fresh = await _make_scan_ready_to_aggregate(db_session, n_total=1, n_evaluated=0)

    await db_session.execute(
        text("UPDATE scans SET updated_at = now() - interval '15 minutes' WHERE id = :id"),
        {"id": stale.id},
    )
    await db_session.commit()

    ctx = _agg_ctx(db_session, arq_pool)
    await jobs.sweep_stalled_scans(ctx)

    # the stale scan (fully evaluated, status="evaluating") should have
    # been pushed to aggregate_scan under reconcile's deterministic id
    stale_dup = await arq_pool.enqueue_job(
        "aggregate_scan", str(stale.id), _job_id=f"agg:{stale.id}:sweep", _queue_name="arq:pipeline"
    )
    assert stale_dup is None

    # the fresh scan (just created, not stale) must be untouched
    fresh_dup = await arq_pool.enqueue_job(
        "aggregate_scan", str(fresh.id), _job_id=f"agg:{fresh.id}:sweep", _queue_name="arq:pipeline"
    )
    assert fresh_dup is not None  # reconcile never ran for it, so this id is still free
