from app.config import settings
from app.core.cost import record_cost_and_check_ceiling


async def test_record_cost_within_budget_returns_true(redis_client):
    assert await record_cost_and_check_ceiling(redis_client, "s1", 0.01) is True


async def test_record_cost_zero_is_a_no_op(redis_client):
    assert await record_cost_and_check_ceiling(redis_client, "s1", 0.0) is True
    assert await redis_client.get("cost:daily") is None


async def test_record_cost_exceeding_scan_ceiling_returns_false(redis_client):
    ok = await record_cost_and_check_ceiling(redis_client, "s1", settings.scan_cost_ceiling_usd + 1)
    assert ok is False


async def test_record_cost_accumulates_across_calls_until_ceiling(redis_client):
    half = settings.scan_cost_ceiling_usd / 2
    assert await record_cost_and_check_ceiling(redis_client, "s1", half) is True
    assert await record_cost_and_check_ceiling(redis_client, "s1", half) is True  # exactly at ceiling, still ok
    assert await record_cost_and_check_ceiling(redis_client, "s1", 0.01) is False  # tips over


async def test_record_cost_exceeding_daily_ceiling_returns_false_even_under_scan_ceiling(redis_client):
    # spread across many different scans so no single scan trips its own
    # ceiling, but the shared daily counter does
    ok = True
    for i in range(int(settings.daily_cost_ceiling_usd) + 2):
        ok = await record_cost_and_check_ceiling(redis_client, f"scan-{i}", 1.0)
    assert ok is False
