import time

FAILURE_THRESHOLD = 5
FAILURE_WINDOW_S = 60
OPEN_DURATION_S = 300


async def record_failure(redis, key_id: str) -> None:
    """5 consecutive failures in 60s -> that key out for 5 min (§13.3).
    Elapsed time past OPEN_DURATION_S naturally reopens to half-open — no extra state."""
    k = f"circuit:{key_id}"
    failures = await redis.hincrby(k, "failures", 1)
    await redis.expire(k, FAILURE_WINDOW_S)
    if failures >= FAILURE_THRESHOLD:
        await redis.hset(k, "opened_at", time.time())
        await redis.expire(k, OPEN_DURATION_S)


async def record_success(redis, key_id: str) -> None:
    await redis.delete(f"circuit:{key_id}")


async def is_key_open(redis, key_id: str) -> bool:
    opened_at = await redis.hget(f"circuit:{key_id}", "opened_at")
    if not opened_at:
        return False
    return time.time() - float(opened_at) < OPEN_DURATION_S


async def is_pool_open(redis, key_ids: list[str]) -> bool:
    """The pool breaker (§10.1) trips only when every key in the pool is down.
    Derived live from key state rather than cached — one Redis round-trip per
    key is cheap at 2-3 keys/pool and keeps this file free of a second source
    of truth. ponytail: recompute-on-read; revisit with a cached circuit:pool:{pool}
    hash only if the ops dashboard (§16) needs trip-history, not just current state."""
    return all([await is_key_open(redis, key_id) for key_id in key_ids])
