from contextlib import asynccontextmanager

ADVANCE_LOCK_TTL_S = 30


async def try_acquire_advance_lock(redis, scan_id: str) -> bool:
    """§9: lock:scan:{id}:advance, SETNX. Prevents two paths (the sweeper's
    reconcile vs. a live job finishing concurrently) from both deciding to
    advance the same scan's state machine at once."""
    return bool(await redis.set(f"lock:scan:{scan_id}:advance", "1", nx=True, ex=ADVANCE_LOCK_TTL_S))


async def release_advance_lock(redis, scan_id: str) -> None:
    await redis.delete(f"lock:scan:{scan_id}:advance")


@asynccontextmanager
async def advance_lock(redis, scan_id: str):
    """Yields True if the lock was acquired (caller should proceed) or False
    if another path already holds it (caller should back off)."""
    acquired = await try_acquire_advance_lock(redis, scan_id)
    try:
        yield acquired
    finally:
        if acquired:
            await release_advance_lock(redis, scan_id)
