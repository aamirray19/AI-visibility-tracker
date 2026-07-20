import redis.asyncio as redis_asyncio

from app.core.ratelimit import record_limits_from_headers, try_acquire, try_acquire_tokens
from tests.conftest import TEST_REDIS_URL

KEY_ID = "k_test"


async def test_try_acquire_allows_up_to_the_rpm_floor(redis_client):
    for _ in range(3):
        assert await try_acquire(redis_client, KEY_ID, rpm_floor=3)
    assert not await try_acquire(redis_client, KEY_ID, rpm_floor=3)


async def test_try_acquire_respects_cooldown(redis_client):
    await redis_client.setex(f"cooldown:{KEY_ID}", 30, "1")
    assert not await try_acquire(redis_client, KEY_ID, rpm_floor=20)


async def test_try_acquire_tokens_respects_tpm_floor(redis_client):
    assert await try_acquire_tokens(redis_client, KEY_ID, tpm_floor=1000, est_tokens=600)
    assert not await try_acquire_tokens(redis_client, KEY_ID, tpm_floor=1000, est_tokens=600)
    assert await try_acquire_tokens(redis_client, KEY_ID, tpm_floor=1000, est_tokens=300)


async def test_try_acquire_tokens_works_with_a_bytes_mode_client(redis_client):
    """The real ARQ worker's ctx["redis"] doesn't set decode_responses=True
    (ARQ needs raw bytes for job pickling), unlike every other test in this
    file which uses the decoded `redis_client` fixture -- that decoded
    fixture is exactly what hid this bug (a real TypeError caught only once
    a real worker ran this code, in Phase 21's live pipeline run)."""
    bytes_client = redis_asyncio.from_url(TEST_REDIS_URL, decode_responses=False)
    try:
        assert await try_acquire_tokens(bytes_client, KEY_ID, tpm_floor=1000, est_tokens=600)
        assert not await try_acquire_tokens(bytes_client, KEY_ID, tpm_floor=1000, est_tokens=600)
        assert await try_acquire_tokens(bytes_client, KEY_ID, tpm_floor=1000, est_tokens=300)
    finally:
        await bytes_client.aclose()


async def test_adaptive_headers_raise_the_ceiling_above_the_floor(redis_client):
    for _ in range(3):
        assert await try_acquire(redis_client, KEY_ID, rpm_floor=3)
    assert not await try_acquire(redis_client, KEY_ID, rpm_floor=3)

    await record_limits_from_headers(redis_client, KEY_ID, {"x-ratelimit-limit-requests": "10"})
    assert await try_acquire(redis_client, KEY_ID, rpm_floor=3)
