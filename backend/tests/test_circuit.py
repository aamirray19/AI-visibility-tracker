from app.core import circuit

KEY_ID = "k_test"


async def test_key_closed_before_threshold(redis_client):
    for _ in range(circuit.FAILURE_THRESHOLD - 1):
        await circuit.record_failure(redis_client, KEY_ID)
    assert not await circuit.is_key_open(redis_client, KEY_ID)


async def test_key_opens_at_threshold(redis_client):
    for _ in range(circuit.FAILURE_THRESHOLD):
        await circuit.record_failure(redis_client, KEY_ID)
    assert await circuit.is_key_open(redis_client, KEY_ID)


async def test_record_success_clears_breaker(redis_client):
    for _ in range(circuit.FAILURE_THRESHOLD):
        await circuit.record_failure(redis_client, KEY_ID)
    await circuit.record_success(redis_client, KEY_ID)
    assert not await circuit.is_key_open(redis_client, KEY_ID)


async def test_pool_open_requires_every_key_down(redis_client):
    for _ in range(circuit.FAILURE_THRESHOLD):
        await circuit.record_failure(redis_client, "k_a")
    assert not await circuit.is_pool_open(redis_client, ["k_a", "k_b"])
