import structlog

from app.core.logging import on_job_end, on_job_start


async def test_on_job_start_binds_attempt_then_on_job_end_clears_it():
    await on_job_start({"job_try": 2})
    assert structlog.contextvars.get_contextvars()["attempt"] == 2

    await on_job_end({"job_try": 2})
    assert structlog.contextvars.get_contextvars() == {}
