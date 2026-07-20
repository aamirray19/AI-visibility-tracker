from app.config import settings

DAILY_COST_KEY = "cost:daily"
DAILY_COST_TTL_S = 24 * 3600
SCAN_COST_TTL_S = 3600


async def _incr_float(redis, key: str, amount: float, *, ttl: int) -> float:
    new_value = await redis.incrbyfloat(key, amount)
    await redis.expire(key, ttl)
    return float(new_value)


async def record_cost_and_check_ceiling(redis, scan_id: str, cost_usd: float) -> bool:
    """§14: cost fuse. Records `cost_usd` against both the per-scan and the
    global daily counters, then returns whether both ceilings still hold.
    "No billing model means no revenue to absorb a runaway loop -- the fuse
    *is* the business control" -- this is a post-hoc check (the call that
    tips the ceiling still completes and gets billed) rather than a
    pre-flight block, since costs aren't known until a response comes back.
    It stops the *next* call, via the caller acting on a False return."""
    if cost_usd <= 0:
        return True
    scan_cost = await _incr_float(redis, f"scan:{scan_id}:cost", cost_usd, ttl=SCAN_COST_TTL_S)
    daily_cost = await _incr_float(redis, DAILY_COST_KEY, cost_usd, ttl=DAILY_COST_TTL_S)
    return scan_cost <= settings.scan_cost_ceiling_usd and daily_cost <= settings.daily_cost_ceiling_usd
