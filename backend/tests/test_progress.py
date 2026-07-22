from app.core import progress


async def test_decrement_returns_remaining_count(arq_pool):
    await arq_pool.set("scan:s1:pending_exec", 3)
    remaining = await progress.decrement(arq_pool, "s1", "pending_exec")
    assert remaining == 2


async def test_decrement_pending_eval_to_zero_enqueues_aggregate_scan(arq_pool):
    await arq_pool.set("scan:s2:pending_eval", 1)
    remaining = await progress.decrement(arq_pool, "s2", "pending_eval")
    assert remaining == 0

    duplicate = await arq_pool.enqueue_job(
        "aggregate_scan", "s2", _job_id="agg:s2", _queue_name="arq:pipeline"
    )
    assert duplicate is None  # already enqueued by decrement()


async def test_decrement_pending_exec_to_zero_does_not_enqueue_aggregate_scan(arq_pool):
    await arq_pool.set("scan:s3:pending_exec", 1)
    remaining = await progress.decrement(arq_pool, "s3", "pending_exec")
    assert remaining == 0

    # not enqueued by decrement() -- this call should succeed (return a real job), not be refused
    job = await arq_pool.enqueue_job(
        "aggregate_scan", "s3", _job_id="agg:s3", _queue_name="arq:pipeline"
    )
    assert job is not None
