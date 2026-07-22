from app.worker.queues import PIPELINE_QUEUE

PROGRESS_TTL_S = 60  # §9: scan:{id}:progress


async def publish(redis, scan_id: str, *, stage: str, done: int = 0, total: int = 0) -> None:
    key = f"scan:{scan_id}:progress"
    await redis.hset(key, mapping={"stage": stage, "done": str(done), "total": str(total)})
    await redis.expire(key, PROGRESS_TTL_S)


async def decrement(redis, scan_id: str, counter: str) -> int:
    """DECR scan:{id}:{counter} (§8's shared `_decr` helper). When
    pending_eval reaches 0, enqueues aggregate_scan -- a deterministic job
    id, harmless to enqueue even before that job exists (Phase 10 fills in
    the real body; Phase 7 already established this enqueue-before-body
    pattern for execute_prompt)."""
    remaining = await redis.decr(f"scan:{scan_id}:{counter}")
    if counter == "pending_eval" and remaining <= 0:
        await redis.enqueue_job("aggregate_scan", scan_id, _job_id=f"agg:{scan_id}", _queue_name=PIPELINE_QUEUE)
    return remaining
