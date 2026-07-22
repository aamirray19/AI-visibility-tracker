import logging
import sys

import structlog

logger = structlog.get_logger("app")


def configure_logging() -> None:
    """§16: structured JSON logs. `scan_id`/`job_name`/`provider`/`attempt`
    are bound via structlog's contextvars (per-request in the API, per-job
    in the worker) so every log line emitted while handling that request/job
    carries them without threading extra params through every call site.
    `scan_id` is the correlation id from the first HTTP request through the
    last evaluation."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def on_job_start(ctx: dict) -> None:
    """ARQ hook: binds `attempt` for every job generically (job_try is
    always accurate here, unlike parsing it out of the job id)."""
    structlog.contextvars.bind_contextvars(attempt=ctx.get("job_try"))


async def on_job_end(ctx: dict) -> None:
    structlog.contextvars.clear_contextvars()
