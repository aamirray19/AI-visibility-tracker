import time

import pytest

from app.core import circuit
from app.core.keypool import Key, KeyPool, PoolExhausted, parse_keys

KEY_A = Key(id="k_a", secret="secret_a", org="org_a")
KEY_B = Key(id="k_b", secret="secret_b", org="org_b")


def test_parse_keys_reads_bare_csv_and_auto_assigns_id_and_org():
    keys = parse_keys("secret_a,secret_b", "pool")
    assert keys == [
        Key(id="pool_1", secret="secret_a", org="pool_1"),
        Key(id="pool_2", secret="secret_b", org="pool_2"),
    ]


def test_parse_keys_empty_string_is_no_keys():
    assert parse_keys("", "pool") == []


async def test_acquire_returns_a_healthy_key(redis_client):
    pool = KeyPool("test_pool", [KEY_A], "failover", rpm=20, tpm=5000)
    key = await pool.acquire(redis_client, est_tokens=100)
    assert key == KEY_A


async def test_round_robin_rotates_across_calls(redis_client):
    pool = KeyPool("rr_pool", [KEY_A, KEY_B], "round_robin", rpm=20, tpm=5000)
    first = await pool.acquire(redis_client, est_tokens=100)
    second = await pool.acquire(redis_client, est_tokens=100)
    assert {first, second} == {KEY_A, KEY_B}
    assert first != second


async def test_failover_always_prefers_key_one(redis_client):
    pool = KeyPool("fo_pool", [KEY_A, KEY_B], "failover", rpm=20, tpm=5000)
    first = await pool.acquire(redis_client, est_tokens=100)
    second = await pool.acquire(redis_client, est_tokens=100)
    assert first == KEY_A
    assert second == KEY_A


async def test_cooldown_key_is_skipped_in_favor_of_next(redis_client):
    await redis_client.setex(f"cooldown:{KEY_A.id}", 30, "1")
    pool = KeyPool("cooldown_pool", [KEY_A, KEY_B], "round_robin", rpm=20, tpm=5000)
    key = await pool.acquire(redis_client, est_tokens=100)
    assert key == KEY_B


async def test_breaker_open_key_is_skipped(redis_client):
    for _ in range(circuit.FAILURE_THRESHOLD):
        await circuit.record_failure(redis_client, KEY_A.id)
    assert await circuit.is_key_open(redis_client, KEY_A.id)

    pool = KeyPool("breaker_pool", [KEY_A, KEY_B], "round_robin", rpm=20, tpm=5000)
    key = await pool.acquire(redis_client, est_tokens=100)
    assert key == KEY_B


async def test_pool_breaker_opens_only_when_every_key_is_down(redis_client):
    for _ in range(circuit.FAILURE_THRESHOLD):
        await circuit.record_failure(redis_client, KEY_A.id)
    assert not await circuit.is_pool_open(redis_client, [KEY_A.id, KEY_B.id])

    for _ in range(circuit.FAILURE_THRESHOLD):
        await circuit.record_failure(redis_client, KEY_B.id)
    assert await circuit.is_pool_open(redis_client, [KEY_A.id, KEY_B.id])


async def test_pool_exhausted_raised_only_after_max_spins(redis_client):
    for _ in range(circuit.FAILURE_THRESHOLD):
        await circuit.record_failure(redis_client, KEY_A.id)
    pool = KeyPool("exhausted_pool", [KEY_A], "failover", rpm=20, tpm=5000, max_spins=1)
    with pytest.raises(PoolExhausted):
        await pool.acquire(redis_client, est_tokens=100)


async def test_acquire_fails_fast_when_every_key_is_already_known_down(redis_client):
    """Regression guard: a pool whose only key is cooling down/breaker-open
    must not pay the ~20s spin-and-backoff budget to learn what one Redis
    round-trip already knows (previously measured at 23s for this exact case)."""
    await redis_client.setex(f"cooldown:{KEY_A.id}", 3600, "1")
    pool = KeyPool("cooldown_only_pool", [KEY_A], "failover", rpm=20, tpm=5000)  # default max_spins=20
    start = time.monotonic()
    with pytest.raises(PoolExhausted):
        await pool.acquire(redis_client, est_tokens=100)
    assert time.monotonic() - start < 1.0


async def test_acquire_still_spins_when_a_key_is_only_rate_limited(redis_client):
    """A key that's neither cooling down nor breaker-open, just RPM/TPM
    saturated, is worth the normal spin-and-backoff wait -- only cooldown/
    breaker state should trigger the fast-fail path."""
    pool = KeyPool("rpm_saturated_pool", [KEY_A], "failover", rpm=1, tpm=5000, max_spins=1)
    await pool.acquire(redis_client, est_tokens=100)  # consumes the one rpm slot
    with pytest.raises(PoolExhausted):
        await pool.acquire(redis_client, est_tokens=100)  # saturated, but not "down" -- still spins once


async def test_acquire_empty_pool_raises_immediately(redis_client):
    pool = KeyPool("empty_pool", [], "failover", rpm=20, tpm=5000)
    start = time.monotonic()
    with pytest.raises(PoolExhausted):
        await pool.acquire(redis_client, est_tokens=100)
    assert time.monotonic() - start < 1.0


async def test_acquire_does_not_burn_rpm_slot_when_tpm_check_fails(redis_client):
    """Regression guard: RPM must not be committed ahead of the TPM check --
    a call that fails on tokens shouldn't leave a phantom request in the RPM
    window for a call that never happened."""
    pool = KeyPool("tpm_starved_pool", [KEY_A], "failover", rpm=5, tpm=10, max_spins=1)
    with pytest.raises(PoolExhausted):
        await pool.acquire(redis_client, est_tokens=1000)  # tpm floor (10) can never cover this
    assert await redis_client.zcard(f"ratelimit:{KEY_A.id}") == 0
