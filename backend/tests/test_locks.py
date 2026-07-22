from app.core.locks import advance_lock, release_advance_lock, try_acquire_advance_lock


async def test_try_acquire_advance_lock_succeeds_when_free(redis_client):
    assert await try_acquire_advance_lock(redis_client, "s1") is True


async def test_try_acquire_advance_lock_fails_when_held(redis_client):
    await try_acquire_advance_lock(redis_client, "s1")
    assert await try_acquire_advance_lock(redis_client, "s1") is False


async def test_release_advance_lock_frees_it(redis_client):
    await try_acquire_advance_lock(redis_client, "s1")
    await release_advance_lock(redis_client, "s1")
    assert await try_acquire_advance_lock(redis_client, "s1") is True


async def test_advance_lock_context_manager_acquires_and_releases(redis_client):
    async with advance_lock(redis_client, "s1") as acquired:
        assert acquired is True
        assert await try_acquire_advance_lock(redis_client, "s1") is False  # held during the block

    assert await try_acquire_advance_lock(redis_client, "s1") is True  # released after


async def test_advance_lock_yields_false_when_already_held(redis_client):
    await try_acquire_advance_lock(redis_client, "s1")
    async with advance_lock(redis_client, "s1") as acquired:
        assert acquired is False

    # the second (failed) context manager must not have released the
    # original holder's lock
    assert await try_acquire_advance_lock(redis_client, "s1") is False
