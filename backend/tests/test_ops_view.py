from sqlalchemy import text


async def test_ops_views_are_queryable(db_session):
    for view in ("ops_scan_status", "ops_provider_stats", "ops_scan_cost"):
        result = await db_session.execute(text(f"SELECT * FROM {view}"))
        assert result.keys() is not None
