import pytest

from app.core.keypool import Key, KeyPool
from app.llm.base import (
    LLMResponse,
    PermanentKeyFailure,
    ProviderCallFailed,
    RateLimited,
    routed_complete,
    strip_code_fence,
)

KEY_A = Key(id="k_a", secret="s_a", org="org_a")
KEY_B = Key(id="k_b", secret="s_b", org="org_b")


def test_strip_code_fence_removes_json_labeled_fence():
    # Gemma (unlike strict Gemini JSON mode) sometimes wraps structured
    # output in a markdown fence even when JSON-only output was requested --
    # a real "trailing characters" ValidationError caught in Phase 21's live run.
    fenced = '```json\n{"verdict": "ok"}\n```'
    assert strip_code_fence(fenced) == '{"verdict": "ok"}'


def test_strip_code_fence_removes_bare_fence():
    fenced = '```\n{"verdict": "ok"}\n```'
    assert strip_code_fence(fenced) == '{"verdict": "ok"}'


def test_strip_code_fence_is_a_noop_on_bare_json():
    bare = '{"verdict": "ok"}'
    assert strip_code_fence(bare) == bare


def test_strip_code_fence_removes_stray_trailing_fence_with_no_opening_fence():
    # Real failure from a live Gemma prompt-gen call: no opening ``` at all,
    # just a stray closing fence appended after the JSON -- the old paired
    # regex required both ends to match and left this one untouched.
    stray = '{"verdict": "ok"}\n```'
    assert strip_code_fence(stray) == '{"verdict": "ok"}'


def make_response(model="gemini-2.5-flash"):
    return LLMResponse(text="ok", tokens_in=100, tokens_out=50, latency_ms=10, model=model)


async def test_success_computes_cost(redis_client):
    pool = KeyPool("p", [KEY_A], "failover", rpm=20, tpm=5000)

    async def raw_call(key):
        return make_response()

    response = await routed_complete(redis_client, pool, raw_call)
    assert response.cost_usd == 0.0  # pricing table is all-zero placeholders until §15.3 rates are filled in


async def test_rate_limited_parks_key_and_falls_through_to_next(redis_client):
    pool = KeyPool("p", [KEY_A, KEY_B], "failover", rpm=20, tpm=5000)
    calls = []

    async def raw_call(key):
        calls.append(key.id)
        if key.id == KEY_A.id:
            raise RateLimited(retry_after_s=30)
        return make_response()

    response = await routed_complete(redis_client, pool, raw_call)
    assert response.text == "ok"
    assert calls == [KEY_A.id, KEY_B.id]
    assert await redis_client.exists(f"cooldown:{KEY_A.id}")


async def test_permanent_failure_disables_key_and_moves_on(redis_client):
    pool = KeyPool("p", [KEY_A, KEY_B], "failover", rpm=20, tpm=5000)

    async def raw_call(key):
        if key.id == KEY_A.id:
            raise PermanentKeyFailure(KEY_A.id)
        return make_response()

    response = await routed_complete(redis_client, pool, raw_call)
    assert response.text == "ok"
    assert await redis_client.exists(f"cooldown:{KEY_A.id}")


async def test_provider_call_failed_trips_the_breaker_and_retries(redis_client):
    pool = KeyPool("p", [KEY_A], "failover", rpm=20, tpm=5000)
    attempts = {"n": 0}

    async def raw_call(key):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise ProviderCallFailed("boom")
        return make_response()

    response = await routed_complete(redis_client, pool, raw_call, max_retries=3)
    assert response.text == "ok"
    assert attempts["n"] == 2


async def test_exhausting_retries_raises_the_last_error(redis_client):
    pool = KeyPool("p", [KEY_A], "failover", rpm=20, tpm=5000)

    async def raw_call(key):
        raise ProviderCallFailed("always fails")

    with pytest.raises(ProviderCallFailed):
        await routed_complete(redis_client, pool, raw_call, max_retries=1)


async def test_rate_limited_never_consumes_the_retry_budget(redis_client):
    """§13.1: a 429 "never consumes an ARQ attempt". With max_retries=3, a run
    of 5 distinct RateLimited responses (each parking a different key) must
    still reach and use a 5th key -- proving 429s aren't counted against the
    same budget as real failures."""
    keys = [Key(id=f"k{i}", secret=f"s{i}", org=f"org{i}") for i in range(5)]
    pool = KeyPool("p", keys, "failover", rpm=20, tpm=5000)
    calls = []

    async def raw_call(key):
        calls.append(key.id)
        if len(calls) < 5:
            raise RateLimited(retry_after_s=30)
        return make_response()

    response = await routed_complete(redis_client, pool, raw_call, max_retries=3)
    assert response.text == "ok"
    assert len(calls) == 5
