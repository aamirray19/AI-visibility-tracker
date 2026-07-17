import time
from uuid import uuid4

LEARNED_LIMIT_TTL_S = 300  # decays back to the cold-start floor if headers stop arriving


async def try_acquire(redis, key_id: str, rpm_floor: int, window_s: int = 60, *, commit: bool = True) -> bool:
    """Non-blocking sliding-window request limiter, keyed per key_id (§9).
    Returns False so the pool can try the NEXT key instead of sleeping on a saturated one.
    `commit=False` peeks without writing -- used by KeyPool.acquire() to check RPM and TPM
    together before committing either, so a call that fails the TPM check doesn't still
    burn an RPM slot for a request that never happened."""
    if await redis.exists(f"cooldown:{key_id}"):
        return False
    rpm = await _learned_or_floor(redis, f"limit:rpm:{key_id}", rpm_floor)
    k, now = f"ratelimit:{key_id}", time.time()
    async with redis.pipeline() as pipe:
        pipe.zremrangebyscore(k, 0, now - window_s)
        pipe.zcard(k)
        _, used = await pipe.execute()
    if used >= rpm:
        return False
    if commit:
        await commit_request(redis, key_id, window_s)
    return True


async def commit_request(redis, key_id: str, window_s: int = 60) -> None:
    now = time.time()
    k = f"ratelimit:{key_id}"
    await redis.zadd(k, {f"{now}:{uuid4()}": now})
    await redis.expire(k, window_s)


async def try_acquire_tokens(
    redis, key_id: str, tpm_floor: int, est_tokens: int, window_s: int = 60, *, commit: bool = True
) -> bool:
    """Same sliding-window shape as try_acquire, summing token counts instead of request counts —
    TPM is the limit that actually binds in practice (§15.1). `commit=False` peeks without writing."""
    tpm = await _learned_or_floor(redis, f"limit:tpm:{key_id}", tpm_floor)
    k, now = f"tokens:{key_id}", time.time()
    async with redis.pipeline() as pipe:
        pipe.zremrangebyscore(k, 0, now - window_s)
        pipe.zrange(k, 0, -1)
        _, entries = await pipe.execute()
    used = sum(int(member.rsplit(":", 1)[1]) for member in entries)
    if used + est_tokens > tpm:
        return False
    if commit:
        await commit_tokens(redis, key_id, est_tokens, window_s)
    return True


async def commit_tokens(redis, key_id: str, est_tokens: int, window_s: int = 60) -> None:
    now = time.time()
    k = f"tokens:{key_id}"
    await redis.zadd(k, {f"{now}:{uuid4()}:{est_tokens}": now})
    await redis.expire(k, window_s)


async def _learned_or_floor(redis, learned_key: str, floor: int) -> int:
    learned = await redis.get(learned_key)
    return int(learned) if learned is not None else floor


DEFAULT_RESET_S = 30  # used only if a reset header is present but unparseable


async def record_limits_from_headers(redis, key_id: str, headers: dict) -> None:
    """Adaptive mode (§15.1): both providers return the current budget on every
    response. `x-ratelimit-limit-*` raises our sliding-window ceiling above the
    cold-start floor. `x-ratelimit-remaining-*` hitting zero means the provider
    says this key is exhausted *right now*, regardless of what our own window
    thinks -- park it via the same cooldown mechanism a 429 uses, for
    `x-ratelimit-reset-*` seconds."""
    limit_requests = headers.get("x-ratelimit-limit-requests")
    limit_tokens = headers.get("x-ratelimit-limit-tokens")
    if limit_requests is not None:
        await redis.setex(f"limit:rpm:{key_id}", LEARNED_LIMIT_TTL_S, str(int(limit_requests)))
    if limit_tokens is not None:
        await redis.setex(f"limit:tpm:{key_id}", LEARNED_LIMIT_TTL_S, str(int(limit_tokens)))

    await _cooldown_if_exhausted(redis, key_id, headers, "x-ratelimit-remaining-requests", "x-ratelimit-reset-requests")
    await _cooldown_if_exhausted(redis, key_id, headers, "x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens")


async def _cooldown_if_exhausted(redis, key_id: str, headers: dict, remaining_header: str, reset_header: str) -> None:
    remaining = headers.get(remaining_header)
    if remaining is None:
        return
    try:
        if float(remaining) > 0:
            return
    except ValueError:
        return
    await redis.setex(f"cooldown:{key_id}", _parse_reset_seconds(headers.get(reset_header)), "1")


def _parse_reset_seconds(raw: str | None) -> int:
    """Reset headers are provider-specific duration strings (Groq's exact format
    is one of the §10 "verify before Phase 21" open items) -- parse a plain
    number of seconds if we can, else fall back to a conservative default
    rather than guessing at a format we haven't seen a real response for."""
    if not raw:
        return DEFAULT_RESET_S
    try:
        return max(1, int(float(raw)))
    except ValueError:
        return DEFAULT_RESET_S
