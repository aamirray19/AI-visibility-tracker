import asyncio
import random
from dataclasses import dataclass

from app.core import circuit, ratelimit

MAX_POOL_SPINS_DEFAULT = 20


@dataclass(frozen=True)
class Key:
    id: str
    secret: str
    org: str


def parse_keys(raw: str, pool_name: str) -> list[Key]:
    """Parse the key-pool env format (§17): comma-separated raw API keys,
    e.g. `AIzaSy...,AIzaSy...`. Each key is auto-assigned an id (`{pool_name}_{n}`)
    and org defaults to that id -- every key is its own bucket, the common
    case per §10.1. Empty string -> no keys."""
    if not raw.strip():
        return []
    keys = []
    for i, entry in enumerate(raw.split(","), start=1):
        secret = entry.strip()
        id_ = f"{pool_name}_{i}"
        keys.append(Key(id=id_, secret=secret, org=id_))
    return keys


class PoolExhausted(Exception):
    def __init__(self, pool_name: str):
        self.pool_name = pool_name
        super().__init__(f"pool exhausted: {pool_name}")


class KeyPool:
    """A pool is the unit of capacity; a key is the unit of failure (§10.1)."""

    def __init__(
        self,
        name: str,
        keys: list[Key],
        strategy: str,
        rpm: int,
        tpm: int,
        max_spins: int = MAX_POOL_SPINS_DEFAULT,
    ):
        self.name = name
        self.keys = keys
        self.strategy = strategy
        self.rpm = rpm
        self.tpm = tpm
        self.max_spins = max_spins

    async def _candidates(self, redis) -> list[Key]:
        if self.strategy == "round_robin" and self.keys:
            cursor = await redis.incr(f"rr:{self.name}")
            start = cursor % len(self.keys)
            return self.keys[start:] + self.keys[:start]
        return self.keys  # failover: always try key 1 first

    async def acquire(self, redis, est_tokens: int) -> Key:
        """Return a healthy, non-saturated key. Raise PoolExhausted only if
        every key is unavailable across every spin.

        Fails immediately, without spinning, if every key is already known to
        be down for a long time (circuit open or cooling down) -- the spin
        loop's ~20s backoff budget exists for transient RPM/TPM saturation
        that can plausibly clear within it, not for a key that won't recover
        for minutes/hours/permanently. Spinning through that case anyway just
        makes every caller (including a human waiting at the verification
        gate, §7.3) pay ~20s to learn what one Redis round-trip already knows.
        """
        if not self.keys or await self._all_down(redis):
            raise PoolExhausted(self.name)

        for _ in range(self.max_spins):
            for key in await self._candidates(redis):
                if await circuit.is_key_open(redis, key.id):
                    continue
                if not await ratelimit.try_acquire(redis, key.id, self.rpm, commit=False):
                    continue
                if not await ratelimit.try_acquire_tokens(redis, key.id, self.tpm, est_tokens, commit=False):
                    continue
                await ratelimit.commit_request(redis, key.id)
                await ratelimit.commit_tokens(redis, key.id, est_tokens)
                return key
            await asyncio.sleep(0.5 + random.random())  # every key busy -> backpressure
        raise PoolExhausted(self.name)

    async def _all_down(self, redis) -> bool:
        for key in self.keys:
            if await circuit.is_key_open(redis, key.id):
                continue
            if await redis.exists(f"cooldown:{key.id}"):
                continue
            return False  # this key is neither breaker-open nor cooling -- worth spinning for
        return True


POOL_SPECS = {
    "google_exec": ("google_exec_keys", "pool_google_exec_strategy"),
    "google_flash": ("google_flash_keys", "pool_google_flash_strategy"),
    "groq_exec": ("groq_exec_keys", "pool_groq_exec_strategy"),
    "groq_eval_a": ("groq_eval_a_keys", "pool_groq_eval_a_strategy"),
    "groq_eval_b": ("groq_eval_b_keys", "pool_groq_eval_b_strategy"),
}


def build_pools(settings) -> dict[str, KeyPool]:
    """One KeyPool per §10.1 pool, built from the comma-separated env vars.
    RPM/TPM start at the cold-start floor; adaptive mode (§15.1) raises the
    ceiling per-key once response headers have been seen."""
    return {
        name: KeyPool(
            name,
            parse_keys(getattr(settings, keys_attr), name),
            getattr(settings, strategy_attr),
            settings.rate_limit_cold_start_rpm,
            settings.rate_limit_cold_start_tpm,
            max_spins=settings.max_pool_spins,
        )
        for name, (keys_attr, strategy_attr) in POOL_SPECS.items()
    }
