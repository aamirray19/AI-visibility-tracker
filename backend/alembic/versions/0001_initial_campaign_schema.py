"""initial campaign schema

Revision ID: 0001_initial_campaign_schema
Revises:
Create Date: 2026-06-22 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_campaign_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    prompt_intent_type = sa.Enum("COMMERCIAL", "INFORMATIONAL", name="prompt_intent_type")
    prompt_status = sa.Enum(
        "PENDING",
        "PROCESSING",
        "COMPLETED",
        "PARTIAL",
        "FAILED",
        name="prompt_status",
    )
    analysis_status = sa.Enum("PENDING", "COMPLETED", "FAILED", name="analysis_status")

    bind = op.get_bind()
    prompt_intent_type.create(bind, checkfirst=True)
    prompt_status.create(bind, checkfirst=True)
    analysis_status.create(bind, checkfirst=True)

    op.create_table(
        "campaign",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("brand_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("prompt_count", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_owner_created_at", "campaign", ["owner_id", "created_at"])
    op.create_index("ix_campaign_owner_id_id", "campaign", ["owner_id", "id"])

    op.create_table(
        "prompt",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("intent_type", prompt_intent_type, nullable=False),
        sa.Column("status", prompt_status, nullable=False, server_default="PENDING"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_prompt_campaign_status", "prompt", ["campaign_id", "status"])
    op.create_index("ix_prompt_campaign_created_at", "prompt", ["campaign_id", "created_at"])

    op.create_table(
        "result",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("prompt.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("response_text", sa.String(), nullable=False),
        sa.Column("brand_mentioned", sa.Boolean(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("mention_context", sa.String(), nullable=True),
        sa.Column("analysis_status", analysis_status, nullable=False, server_default="PENDING"),
        sa.Column("provider_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_result_prompt_provider", "result", ["prompt_id", "provider"])
    op.create_index("ix_result_created_at", "result", ["created_at"])

    op.create_table(
        "cited_url",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("result_id", sa.Integer(), sa.ForeignKey("result.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("source_provider", sa.String(length=100), nullable=False),
        sa.Column("is_target_brand", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("citation_type", sa.String(length=100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cited_url_result_id", "cited_url", ["result_id"])
    op.create_index("ix_cited_url_domain", "cited_url", ["domain"])
    op.create_index("ix_cited_url_is_target_brand", "cited_url", ["is_target_brand"])

    op.create_table(
        "competitor_mention",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("result_id", sa.Integer(), sa.ForeignKey("result.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_name", sa.String(length=255), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_competitor_mention_result_id", "competitor_mention", ["result_id"])
    op.create_index("ix_competitor_mention_brand_name", "competitor_mention", ["brand_name"])


def downgrade() -> None:
    op.drop_index("ix_competitor_mention_brand_name", table_name="competitor_mention")
    op.drop_index("ix_competitor_mention_result_id", table_name="competitor_mention")
    op.drop_table("competitor_mention")

    op.drop_index("ix_cited_url_is_target_brand", table_name="cited_url")
    op.drop_index("ix_cited_url_domain", table_name="cited_url")
    op.drop_index("ix_cited_url_result_id", table_name="cited_url")
    op.drop_table("cited_url")

    op.drop_index("ix_result_created_at", table_name="result")
    op.drop_index("ix_result_prompt_provider", table_name="result")
    op.drop_table("result")

    op.drop_index("ix_prompt_campaign_created_at", table_name="prompt")
    op.drop_index("ix_prompt_campaign_status", table_name="prompt")
    op.drop_table("prompt")

    op.drop_index("ix_campaign_owner_id_id", table_name="campaign")
    op.drop_index("ix_campaign_owner_created_at", table_name="campaign")
    op.drop_table("campaign")

    bind = op.get_bind()
    sa.Enum(name="analysis_status").drop(bind, checkfirst=True)
    sa.Enum(name="prompt_status").drop(bind, checkfirst=True)
    sa.Enum(name="prompt_intent_type").drop(bind, checkfirst=True)
