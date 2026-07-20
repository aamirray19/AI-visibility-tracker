import sentry_sdk
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.core.keypool import build_pools
from app.core.logging import configure_logging, on_job_end, on_job_start
from app.llm.google import GoogleAIStudioProvider
from app.llm.groq import GroqProvider
from app.worker.jobs import (
    aggregate_scan,
    enrich_company,
    evaluate_response,
    execute_prompt,
    finalize_scan,
    generate_prompts,
    sweep_stalled_scans,
    verify_profile,
)
from app.worker.queues import INTERACTIVE_QUEUE, PIPELINE_QUEUE

REDIS_SETTINGS = RedisSettings.from_dsn(settings.redis_url)

configure_logging()
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)


async def on_startup(ctx: dict) -> None:
    engine = create_async_engine(settings.database_url)
    ctx["engine"] = engine
    ctx["db_session_factory"] = async_sessionmaker(engine, expire_on_commit=False)

    pools = build_pools(settings)
    ctx["providers"] = {
        "enrichment": GoogleAIStudioProvider(ctx["redis"], pools["google_flash"], settings.model_enrichment),
        "verification": GoogleAIStudioProvider(ctx["redis"], pools["google_flash"], settings.model_verification),
        "prompt_gen": GoogleAIStudioProvider(ctx["redis"], pools["google_flash"], settings.model_prompt_gen),
        "execution": {
            "google_ai_studio": GoogleAIStudioProvider(ctx["redis"], pools["google_exec"], settings.model_exec_google),
            "groq": GroqProvider(ctx["redis"], pools["groq_exec"], settings.model_exec_groq),
        },
        "evaluation": {
            "eval_a": GroqProvider(ctx["redis"], pools["groq_eval_a"], settings.model_evaluation),
            "eval_b": GroqProvider(ctx["redis"], pools["groq_eval_b"], settings.model_evaluation),
        },
    }


async def on_shutdown(ctx: dict) -> None:
    await ctx["engine"].dispose()


class InteractiveSettings:
    """Human-gated jobs (§8) -- must never queue behind the bulk pipeline.
    Also runs the sweeper cron (§13.4): every 2 min is frequent enough to
    catch a stalled scan quickly without meaningfully competing with the
    human-gated jobs it shares a queue with."""

    functions = [enrich_company, verify_profile]
    cron_jobs = [cron(sweep_stalled_scans, minute=set(range(0, 60, 2)))]
    redis_settings = REDIS_SETTINGS
    queue_name = INTERACTIVE_QUEUE
    job_timeout = 60
    max_jobs = 5
    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end


class PipelineSettings:
    """Bulk execution/evaluation jobs (§8)."""

    functions = [generate_prompts, execute_prompt, evaluate_response, aggregate_scan, finalize_scan]
    redis_settings = REDIS_SETTINGS
    queue_name = PIPELINE_QUEUE
    job_timeout = 120
    max_jobs = 20
    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end
