"""ops view

Revision ID: e4d48cf2c05b
Revises: 86c959ab049c
Create Date: 2026-07-18 11:26:46.364951

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e4d48cf2c05b'
down_revision: Union[str, None] = '86c959ab049c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # §16 ops dashboard. Duration is measured created_at -> finished_at since
    # scans.started_at is never populated by any job (ponytail: wire it up if
    # a "time spent enriching/verifying" breakdown is ever needed). Breaker
    # trips live only in Redis (app/core/circuit.py) -- not derivable from a
    # Postgres view, so they're excluded here; the ops dashboard reads those
    # directly from Redis.
    op.execute(
        """
        CREATE VIEW ops_scan_status AS
        SELECT
            status,
            count(*) AS scan_count,
            percentile_cont(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (finished_at - created_at))
            ) FILTER (WHERE finished_at IS NOT NULL) AS p50_duration_s,
            percentile_cont(0.95) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (finished_at - created_at))
            ) FILTER (WHERE finished_at IS NOT NULL) AS p95_duration_s
        FROM scans
        GROUP BY status
        """
    )
    op.execute(
        """
        CREATE VIEW ops_provider_stats AS
        SELECT
            provider,
            count(*) AS response_count,
            count(*) FILTER (WHERE status = 'success')::float / NULLIF(count(*), 0) AS success_rate,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms
        FROM ai_responses
        GROUP BY provider
        """
    )
    op.execute(
        """
        CREATE VIEW ops_scan_cost AS
        SELECT scan_id, sum(cost_usd) AS total_cost_usd
        FROM ai_responses
        GROUP BY scan_id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops_scan_cost")
    op.execute("DROP VIEW IF EXISTS ops_provider_stats")
    op.execute("DROP VIEW IF EXISTS ops_scan_status")
