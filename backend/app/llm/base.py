import asyncio
import random
import re
from collections.abc import Awaitable, Callable
from typing import Protocol

from pydantic import BaseModel

from app.core import pricing
from app.core.circuit import record_failure, record_success
from app.core.keypool import Key, KeyPool

_LEADING_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?")
_TRAILING_FENCE_RE = re.compile(r"\n?```\s*$")


def strip_code_fence(text: str) -> str:
    """Some models (notably Gemma, less strict than Gemini's true JSON mode)
    wrap structured output in a markdown code fence even when JSON-only
    output was requested, breaking every `model_validate_json(text)` call
    site with "trailing characters" -- a real failure caught in Phase 21's
    live run. Leading and trailing fences are stripped independently since
    some responses carry only a stray trailing ``` with no matching opening
    fence (also seen live) -- a single paired regex misses that case
    entirely. A no-op on already-bare JSON, so every caller can apply this
    unconditionally."""
    stripped = text.strip()
    stripped = _LEADING_FENCE_RE.sub("", stripped, count=1)
    stripped = _TRAILING_FENCE_RE.sub("", stripped, count=1)
    return stripped.strip()


class LLMResponse(BaseModel):
    text: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int
    model: str
    citations: list[dict] = []
    cost_usd: float = 0.0
    key_id: str | None = None  # which pool key served this (never the secret) -- §10.1


class LLMProvider(Protocol):
    name: str
    model: str

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema: type[BaseModel] | None = None,
        tools: list[str] | None = None,
        temperature: float | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse: ...


class PermanentKeyFailure(Exception):
    """401/403/spend-block. The key must never be retried (§10.1)."""

    def __init__(self, key_id: str):
        self.key_id = key_id
        super().__init__(f"key permanently disabled: {key_id}")


class ProviderCallFailed(Exception):
    """5xx / timeout / connection error on a key that's otherwise still usable."""


class RateLimited(Exception):
    """429 with a Retry-After. Not a failure -- the router parks the key and
    immediately retries on the next one (§13.1)."""

    def __init__(self, retry_after_s: int):
        self.retry_after_s = retry_after_s


PERMANENT_COOLDOWN_S = 365 * 24 * 3600

RawCall = Callable[[Key], Awaitable[LLMResponse]]


async def routed_complete(
    redis,
    pool: KeyPool,
    raw_call: RawCall,
    *,
    est_tokens: int = 1000,
    max_retries: int = 3,
) -> LLMResponse:
    """cost tracking -> key-pool router -> retry -> timeout -> raw client (§10).

    `raw_call(key)` is the provider's own HTTP call (already timeout-wrapped);
    it raises RateLimited / PermanentKeyFailure / ProviderCallFailed so this
    router can react per §13.1's retry table. A retried call lands on a
    different key because each loop iteration re-acquires from the pool.

    A 429 (RateLimited) never consumes `max_retries` -- §13.1 is explicit that
    it "never consumes an ARQ attempt" and is "not a sleep". It loops
    unbounded here, but that's not actually unbounded in practice: once every
    key in the pool is cooling down, the next pool.acquire() raises
    PoolExhausted immediately (see KeyPool._all_down), which *does* end the
    call. PermanentKeyFailure and ProviderCallFailed are real failures and do
    count against max_retries.
    """
    last_error: Exception | None = None
    attempts_used = 0
    while True:
        key = await pool.acquire(redis, est_tokens)
        try:
            response = await raw_call(key)
        except RateLimited as exc:
            await redis.setex(f"cooldown:{key.id}", exc.retry_after_s, "1")
            last_error = exc
            continue
        except PermanentKeyFailure as exc:
            await redis.setex(f"cooldown:{key.id}", PERMANENT_COOLDOWN_S, "1")
            last_error = exc
            attempts_used += 1
        except ProviderCallFailed as exc:
            await record_failure(redis, key.id)
            last_error = exc
            attempts_used += 1
            await asyncio.sleep(2 ** (attempts_used - 1) + random.random())
        else:
            await record_success(redis, key.id)
            response.cost_usd = pricing.estimate_cost_usd(
                response.model, response.tokens_in or 0, response.tokens_out or 0
            )
            response.key_id = key.id
            return response
        if attempts_used >= max_retries:
            raise last_error
