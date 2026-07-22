import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from structlog.contextvars import bind_contextvars

from app.config import settings
from app.core import cost, progress
from app.core.error_codes import COST_CEILING_EXCEEDED, SCAN_FAILED
from app.core.keypool import PoolExhausted
from app.core.lifecycle import transition
from app.core.locks import advance_lock
from app.db.models import Scan
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.evaluations import EvaluationRepository
from app.db.repositories.mentions import MentionRepository
from app.db.repositories.metrics import ScanMetricsRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.prompts import PromptRepository
from app.db.repositories.responses import AIResponseRepository
from app.db.repositories.scans import ScanRepository
from app.services import aggregation, entity_resolution, enrichment, evaluation, execution, prompt_gen, verification
from app.worker.queues import PIPELINE_QUEUE

# §10: the two execution providers every prompt fans out to.
EXEC_PROVIDERS = ("google_ai_studio", "groq")
PENDING_COUNTER_TTL_S = 3600
EVAL_DEFER_BASE_S = 30
AGGREGATE_RETRY_DELAY_S = 60
STALLED_STATUSES = ("executing", "evaluating", "aggregating")
STALLED_AFTER_MINUTES = 10


async def enrich_company(ctx: dict, scan_id: str) -> None:
    """First stage of the pipeline (§7.2, §8): created -> enriching ->
    awaiting_verification (or failed). Runs on arq:interactive so it never
    queues behind the bulk execution/evaluation jobs."""
    bind_contextvars(job_name="enrich_company", scan_id=scan_id)
    session_factory = ctx["db_session_factory"]
    redis = ctx["redis"]
    provider = ctx["providers"]["enrichment"]

    async with session_factory() as session:
        scans = ScanRepository(session)
        companies = CompanyRepository(session)
        profiles = CompanyProfileRepository(session)

        scan = await scans.get(uuid.UUID(scan_id))
        company = await companies.get(scan.company_id)

        transition(scan, "enriching")
        await session.commit()
        await progress.publish(redis, scan_id, stage="enriching", done=0, total=1)

        try:
            profile_fields = await enrichment.enrich(redis, provider, name=company.name, domain=company.domain)
        except Exception:
            transition(scan, "failed")
            scan.error_code = SCAN_FAILED
            await session.commit()
            await progress.publish(redis, scan_id, stage="failed", done=0, total=1)
            raise

        await profiles.create(scan_id=scan.id, version=1, source="ai_generated", **profile_fields)
        transition(scan, "awaiting_verification")
        await session.commit()
        await progress.publish(redis, scan_id, stage="awaiting_verification", done=1, total=1)


async def verify_profile(ctx: dict, scan_id: str) -> None:
    """§7.3 step 3: sends the user-edited profile to the critic. issues_found
    -> back to awaiting_verification with issues attached to that profile
    row; ok -> writes v3 and freezes scan_entities (§11)."""
    bind_contextvars(job_name="verify_profile", scan_id=scan_id)
    session_factory = ctx["db_session_factory"]
    redis = ctx["redis"]
    provider = ctx["providers"]["verification"]

    async with session_factory() as session:
        scans = ScanRepository(session)
        companies = CompanyRepository(session)
        profiles = CompanyProfileRepository(session)

        scan = await scans.get(uuid.UUID(scan_id))
        company = await companies.get(scan.company_id)
        latest = await profiles.get_latest(scan.id)

        try:
            result = await verification.critique(provider, company_name=company.name, profile=latest)
        except Exception:
            transition(scan, "failed")
            scan.error_code = SCAN_FAILED
            await session.commit()
            await progress.publish(redis, scan_id, stage="failed", done=0, total=1)
            raise

        if result.verdict == "issues_found":
            latest.issues = [issue.model_dump() for issue in result.issues]
            transition(scan, "awaiting_verification")
        else:
            await verification.accept(session, scan, company, latest)

        await session.commit()
        await progress.publish(redis, scan_id, stage=scan.status, done=1, total=1)


async def generate_prompts(ctx: dict, scan_id: str) -> None:
    """§7.5/§7.6/§8: queued -> generating_prompts -> executing (or failed).
    Writes ~50 validated prompts, fans out 2x execute_prompt jobs per prompt,
    and seeds the pending_exec/pending_eval counters those jobs decrement."""
    bind_contextvars(job_name="generate_prompts", scan_id=scan_id)
    session_factory = ctx["db_session_factory"]
    redis = ctx["redis"]
    provider = ctx["providers"]["prompt_gen"]

    async with session_factory() as session:
        scans = ScanRepository(session)
        entities = ScanEntityRepository(session)
        profiles = CompanyProfileRepository(session)
        prompts = PromptRepository(session)

        scan = await scans.get(uuid.UUID(scan_id))
        transition(scan, "generating_prompts")
        await session.commit()
        await progress.publish(redis, scan_id, stage="generating_prompts", done=0, total=1)

        entity_rows = await entities.list(scan_id=scan.id)
        target = next(e for e in entity_rows if e.is_target)
        competitor_entities = [e for e in entity_rows if not e.is_target]
        brand_only = len(competitor_entities) == 0
        latest_profile = await profiles.get_latest(scan.id)

        try:
            accepted, warnings = await prompt_gen.generate(
                provider,
                company_name=target.name,
                industry=latest_profile.industry if latest_profile else None,
                competitors=[e.name for e in competitor_entities],
                scope_categories=scan.monitoring_categories,
                brand_only=brand_only,
                target_count=settings.prompt_count,
            )
        except Exception:
            transition(scan, "failed")
            scan.error_code = SCAN_FAILED
            await session.commit()
            await progress.publish(redis, scan_id, stage="failed", done=0, total=1)
            raise

        scan.brand_only = brand_only
        if warnings:
            scan.status_detail = ",".join(warnings)

        created_prompts = [
            await prompts.create(
                scan_id=scan.id, text=p["text"], category=p["category"], target=p["target"], dedupe_hash=p["dedupe_hash"]
            )
            for p in accepted
        ]

        fanout = [(p.id, exec_provider) for p in created_prompts for exec_provider in EXEC_PROVIDERS]
        await redis.set(f"scan:{scan_id}:pending_exec", len(fanout), ex=PENDING_COUNTER_TTL_S)
        await redis.set(f"scan:{scan_id}:pending_eval", len(fanout), ex=PENDING_COUNTER_TTL_S)
        for prompt_id, exec_provider in fanout:
            await redis.enqueue_job(
                "execute_prompt",
                scan_id,
                str(prompt_id),
                exec_provider,
                _job_id=f"exec:{prompt_id}:{exec_provider}",
                _queue_name=PIPELINE_QUEUE,
            )

        transition(scan, "executing")
        await session.commit()
        await progress.publish(redis, scan_id, stage="executing", done=0, total=len(fanout))


async def execute_prompt(ctx: dict, scan_id: str, prompt_id: str, provider: str) -> None:
    """§7.7/§13.1/§13.3: the execution fan-out target. Checks cancellation,
    calls the provider, upserts ai_responses, fans out evaluate_response on
    success, and decrements the pending counters (§8's shared `_decr`)."""
    bind_contextvars(job_name="execute_prompt", scan_id=scan_id, provider=provider)
    session_factory = ctx["db_session_factory"]
    redis = ctx["redis"]
    provider_map = ctx["providers"]["execution"]

    if await redis.exists(f"scan:{scan_id}:cancelled"):
        return

    async with session_factory() as session:
        prompts = PromptRepository(session)
        responses = AIResponseRepository(session)

        prompt_row = await prompts.get(uuid.UUID(prompt_id))
        fields = await execution.execute(provider_map[provider], provider, prompt_row.text)
        response_row = await responses.upsert(
            scan_id=uuid.UUID(scan_id), prompt_id=prompt_row.id, provider=provider, **fields
        )
        await session.commit()

    # §14: cost fuse, checked after this call (cost isn't known until the
    # response comes back) -- blocks further spend via the same cooperative
    # cancellation flag execute_prompt already checks on entry, and closes
    # the scan out immediately rather than leaving it to stall.
    if fields.get("cost_usd") and not await cost.record_cost_and_check_ceiling(redis, scan_id, fields["cost_usd"]):
        await redis.setex(f"scan:{scan_id}:cancelled", PENDING_COUNTER_TTL_S, "1")
        async with session_factory() as session:
            scans = ScanRepository(session)
            scan = await scans.get(uuid.UUID(scan_id))
            if scan.status not in ("failed", "completed", "completed_with_gaps", "cancelled"):
                transition(scan, "failed")
                scan.error_code = COST_CEILING_EXCEEDED
                await session.commit()
        return

    if fields["status"] == "success":
        await redis.enqueue_job(
            "evaluate_response",
            str(response_row.id),
            _job_id=f"eval:{response_row.id}",
            _queue_name=PIPELINE_QUEUE,
        )
    else:
        await progress.decrement(redis, scan_id, "pending_eval")

    remaining_exec = await progress.decrement(redis, scan_id, "pending_exec")
    if remaining_exec <= 0:
        # §5: executing -> evaluating (overlapped -- evaluation may already
        # be running on earlier responses by the time the last execution
        # finishes). Guarded so a race between two "last" decrements can't
        # double-transition.
        async with session_factory() as session:
            scans = ScanRepository(session)
            scan = await scans.get(uuid.UUID(scan_id))
            if scan.status == "executing":
                transition(scan, "evaluating")
                await session.commit()


async def evaluate_response(ctx: dict, response_id: str) -> None:
    """§7.9/§11/§13.3: Stage A (deterministic string match) + Stage B (LLM
    critic) evaluation. Stage A is authoritative for target_mentioned and
    known-competitor mentions; Stage B is authoritative for sentiment/rank/
    recommendation. Fans out mentions, decrements pending_eval.

    Idempotent: if an evaluation already exists for this response, this is a
    no-op -- re-running (e.g. a stray duplicate job) must not double-write
    mentions or violate evaluations.response_id's unique constraint."""
    bind_contextvars(job_name="evaluate_response", response_id=response_id)
    session_factory = ctx["db_session_factory"]
    redis = ctx["redis"]

    async with session_factory() as session:
        responses = AIResponseRepository(session)
        prompts = PromptRepository(session)
        entities = ScanEntityRepository(session)
        evaluations = EvaluationRepository(session)
        mentions = MentionRepository(session)

        response = await responses.get(uuid.UUID(response_id))

        if await redis.exists(f"scan:{response.scan_id}:cancelled"):
            return

        if await evaluations.get_by_response(response.id):
            return

        bind_contextvars(scan_id=str(response.scan_id), provider=response.provider)
        prompt_row = await prompts.get(response.prompt_id)
        entity_rows = await entities.list(scan_id=response.scan_id)
        target_entity = next(e for e in entity_rows if e.is_target)
        raw_response = response.raw_response or ""

        target_mentioned, stage_a_matches = evaluation.stage_a(raw_response, entity_rows)
        pool_name = evaluation.evaluator_pool_for(response.provider)
        provider = ctx["providers"]["evaluation"][pool_name]

        try:
            result = await evaluation.stage_b(
                provider,
                prompt_text=prompt_row.text,
                response_text=raw_response,
                target_name=target_entity.name,
                target_mentioned=target_mentioned,
            )
        except PoolExhausted:
            # §13.3: defer, don't skip -- an unevaluated response silently
            # biases every downstream metric, unlike a skipped execution.
            attempts = await redis.incr(f"eval_defer_attempts:{response_id}")
            defer_by = min(EVAL_DEFER_BASE_S * (2 ** (attempts - 1)), settings.eval_max_defer_s)
            await redis.enqueue_job(
                "evaluate_response",
                response_id,
                _job_id=f"eval:{response_id}:retry:{attempts}",
                _defer_by=defer_by,
                _queue_name=PIPELINE_QUEUE,
            )
            return

        evaluation_row = await evaluations.create(
            scan_id=response.scan_id,
            response_id=response.id,
            sentiment=result.sentiment if target_mentioned else None,
            target_mentioned=target_mentioned,
            recommended=result.recommended if target_mentioned else False,
            rank_position=result.rank_position if target_mentioned else None,
            confidence=result.confidence,
            reasoning=result.reasoning,
            mentioned_companies=result.mentioned_companies,
            evaluator_model=provider.model,
            evaluator_pool=pool_name,
        )

        recorded_entity_ids: set[uuid.UUID] = set()
        for entity in stage_a_matches:
            await mentions.create(
                scan_id=response.scan_id,
                evaluation_id=evaluation_row.id,
                response_id=response.id,
                entity_id=entity.id,
                raw_name=entity.name,
                is_target=entity.is_target,
                rank_position=result.rank_position if entity.is_target else None,
                sentiment=result.sentiment if entity.is_target else None,
            )
            recorded_entity_ids.add(entity.id)

        for raw_name in result.mentioned_companies:
            resolved = entity_resolution.resolve_mention(
                raw_name, entities=entity_rows, text=raw_response, citations=response.citations
            )
            if resolved and resolved.id in recorded_entity_ids:
                continue  # already recorded via Stage A -- don't double-count
            await mentions.create(
                scan_id=response.scan_id,
                evaluation_id=evaluation_row.id,
                response_id=response.id,
                entity_id=resolved.id if resolved else None,
                raw_name=raw_name,
                is_target=bool(resolved and resolved.is_target),
            )
            if resolved:
                recorded_entity_ids.add(resolved.id)

        scan_id = str(response.scan_id)
        await session.commit()

    await progress.decrement(redis, scan_id, "pending_eval")


async def aggregate_scan(ctx: dict, scan_id: str) -> None:
    """§8/§12: early-fire guard -- SQL is authoritative, not the counter
    that woke this job. A crashed job or a double-DECR could make
    pending_eval hit zero before every evaluation is actually written, and
    an early aggregate would silently publish a dashboard computed on half
    the data. Once genuinely caught up: compute + upsert scan_metrics
    (idempotent), then enqueue finalize_scan.

    A cancelled scan skips the guard entirely: evaluate_response also bails
    on cancellation, so any response left un-evaluated when the flag was set
    will never be evaluated -- waiting for evaluated==total would retry
    forever. Aggregate over whatever exists instead."""
    bind_contextvars(job_name="aggregate_scan", scan_id=scan_id)
    session_factory = ctx["db_session_factory"]
    redis = ctx["redis"]
    scan_uuid = uuid.UUID(scan_id)
    cancelled = bool(await redis.exists(f"scan:{scan_id}:cancelled"))

    async with session_factory() as session:
        responses = AIResponseRepository(session)
        evaluations = EvaluationRepository(session)
        total = len(await responses.list(scan_id=scan_uuid))
        evaluated = len(await evaluations.list(scan_id=scan_uuid))

    if evaluated < total and not cancelled:
        # ponytail: retries indefinitely at a fixed 60s cadence rather than
        # tracking an explicit deadline; Phase 12's sweeper is the real
        # backstop for a scan that's stuck for good.
        retry_n = await redis.incr(f"scan:{scan_id}:agg_retries")
        await redis.enqueue_job(
            "aggregate_scan",
            scan_id,
            _defer_by=AGGREGATE_RETRY_DELAY_S,
            _job_id=f"agg:{scan_id}:retry:{retry_n}",
            _queue_name=PIPELINE_QUEUE,
        )
        return

    async with session_factory() as session:
        scans = ScanRepository(session)
        scan = await scans.get(scan_uuid)
        if scan.status == "executing":
            # a scan cancelled before its last execute_prompt could ever
            # decrement pending_exec to 0 never naturally reaches
            # "evaluating" -- catch it up here rather than teaching every
            # caller (reconcile included) that nuance.
            transition(scan, "evaluating")
        transition(scan, "aggregating")
        await session.commit()

        rates = await aggregation.provider_rates(session, scan_uuid)
        _, excluded, _ = aggregation.decide_outcome(rates)
        metrics = await aggregation.compute_metrics(session, scan_uuid, excluded_providers=excluded)
        metrics["brand_only"] = scan.brand_only

        scan_metrics = ScanMetricsRepository(session)
        existing = await scan_metrics.get(scan_uuid)
        if existing:
            existing.metrics = metrics
        else:
            await scan_metrics.create(scan_id=scan_uuid, metrics=metrics)
        await session.commit()

    await redis.enqueue_job("finalize_scan", scan_id, _job_id=f"finalize:{scan_id}", _queue_name=PIPELINE_QUEUE)


async def finalize_scan(ctx: dict, scan_id: str) -> None:
    """§13.2/§7.10: applies the partial-results decision table to close out
    the lifecycle, sets finished_at, writes the deferred scan:recent:{domain}
    cache (§7.1's reuse mechanism), and clears the progress cache."""
    bind_contextvars(job_name="finalize_scan", scan_id=scan_id)
    session_factory = ctx["db_session_factory"]
    redis = ctx["redis"]
    scan_uuid = uuid.UUID(scan_id)

    async with session_factory() as session:
        scans = ScanRepository(session)
        companies = CompanyRepository(session)
        scan = await scans.get(scan_uuid)
        company = await companies.get(scan.company_id)

        rates = await aggregation.provider_rates(session, scan_uuid)
        status, _, detail = aggregation.decide_outcome(rates)

        transition(scan, status)
        if detail:
            scan.status_detail = detail
        scan.finished_at = datetime.now(UTC)
        await session.commit()

    await redis.delete(f"scan:{scan_id}:progress")
    if status in ("completed", "completed_with_gaps"):
        await redis.setex(
            f"scan:recent:{company.domain}", settings.scan_reuse_ttl_hours * 3600, str(scan_uuid)
        )


async def reconcile(ctx: dict, scan_id: str, status: str) -> None:
    """§13.4: recomputes truth from Postgres for one stalled scan and either
    re-enqueues exactly the missing jobs (deterministic `_job_id`s make this
    a no-op if they're already queued) or pushes the pipeline forward a
    step. Guarded by the advance lock (§9) so the sweeper can't race a live
    job that's mid-transition on the same scan.

    A cancelled scan is never "recovered" -- re-enqueueing its missing work
    would defeat the whole point of cancelling. It gets pushed straight to
    aggregate_scan/finalize_scan to close out with whatever partial data
    already exists."""
    bind_contextvars(job_name="reconcile", scan_id=scan_id)
    session_factory = ctx["db_session_factory"]
    redis = ctx["redis"]
    scan_uuid = uuid.UUID(scan_id)

    async with advance_lock(redis, scan_id) as acquired:
        if not acquired:
            return

        cancelled = bool(await redis.exists(f"scan:{scan_id}:cancelled"))

        async with session_factory() as session:
            prompts_repo = PromptRepository(session)
            responses_repo = AIResponseRepository(session)
            evaluations_repo = EvaluationRepository(session)
            metrics_repo = ScanMetricsRepository(session)

            prompt_rows = await prompts_repo.list(scan_id=scan_uuid)
            response_rows = await responses_repo.list(scan_id=scan_uuid)
            eval_rows = await evaluations_repo.list(scan_id=scan_uuid)
            existing_metrics = await metrics_repo.get(scan_uuid)

        if status == "executing" and not cancelled:
            existing_keys = {(r.prompt_id, r.provider) for r in response_rows}
            missing = [
                (p.id, provider)
                for p in prompt_rows
                for provider in EXEC_PROVIDERS
                if (p.id, provider) not in existing_keys
            ]
            for prompt_id, provider in missing:
                await redis.enqueue_job(
                    "execute_prompt", scan_id, str(prompt_id), provider,
                    _job_id=f"exec:{prompt_id}:{provider}", _queue_name=PIPELINE_QUEUE,
                )
            if missing:
                return

        if status in ("executing", "evaluating") and not cancelled:
            successful = [r for r in response_rows if r.status == "success"]
            evaluated_response_ids = {e.response_id for e in eval_rows}
            missing_eval = [r.id for r in successful if r.id not in evaluated_response_ids]
            for response_id in missing_eval:
                await redis.enqueue_job(
                    "evaluate_response", str(response_id),
                    _job_id=f"eval:{response_id}", _queue_name=PIPELINE_QUEUE,
                )
            if missing_eval:
                return

        if existing_metrics is None:
            await redis.enqueue_job(
                "aggregate_scan", scan_id,
                _job_id=f"agg:{scan_id}:sweep", _queue_name=PIPELINE_QUEUE,
            )
        else:
            await redis.enqueue_job(
                "finalize_scan", scan_id, _job_id=f"finalize:{scan_id}", _queue_name=PIPELINE_QUEUE
            )


async def sweep_stalled_scans(ctx: dict) -> None:
    """§13.4: cron, every 2 min. This one job is what makes the system
    self-healing across worker crashes/deploys -- every job is idempotent
    and every job id is deterministic, so reconciling is always safe."""
    bind_contextvars(job_name="sweep_stalled_scans")
    session_factory = ctx["db_session_factory"]

    async with session_factory() as session:
        cutoff = datetime.now(UTC) - timedelta(minutes=STALLED_AFTER_MINUTES)
        stmt = select(Scan.id, Scan.status).where(
            Scan.status.in_(STALLED_STATUSES),
            Scan.updated_at < cutoff,
        )
        stalled = (await session.execute(stmt)).all()

    for scan_id, status in stalled:
        await reconcile(ctx, str(scan_id), status)
