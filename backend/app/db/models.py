import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


def _created_at() -> Mapped[datetime]:
    return mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_norm: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = _created_at()


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="created")
    status_detail: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    monitoring_categories: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    brand_only: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    progress: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        Index("ix_scans_company_id_finished_at", "company_id", "finished_at"),
        Index("ix_scans_status", "status"),
    )


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    products: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    competitors: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    warnings: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    issues: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    raw_model_out: Mapped[dict | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint("scan_id", "version", name="uq_company_profiles_scan_version"),
        CheckConstraint(
            "source in ('ai_generated','user_edited','ai_verified')", name="ck_company_profiles_source"
        ),
    )


class ScanEntity(Base):
    __tablename__ = "scan_entities"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_norm: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    is_target: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    __table_args__ = (Index("ix_scan_entities_scan_id", "scan_id"),)


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(Text)
    target: Mapped[str | None] = mapped_column(Text)
    dedupe_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint("scan_id", "dedupe_hash", name="uq_prompts_scan_dedupe_hash"),
        Index("ix_prompts_scan_id", "scan_id"),
    )


class AIResponse(Base):
    __tablename__ = "ai_responses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error_code: Mapped[str | None] = mapped_column(Text)
    api_key_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint("prompt_id", "provider", name="uq_ai_responses_prompt_provider"),
        Index("ix_ai_responses_scan_provider_status", "scan_id", "provider", "status"),
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_responses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    sentiment: Mapped[str | None] = mapped_column(Text)
    target_mentioned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    rank_position: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    reasoning: Mapped[str | None] = mapped_column(Text)
    mentioned_companies: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    evaluator_model: Mapped[str | None] = mapped_column(Text)
    evaluator_pool: Mapped[str | None] = mapped_column(Text)
    api_key_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_responses.id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scan_entities.id"))
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_target: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    rank_position: Mapped[int | None] = mapped_column(Integer)
    sentiment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_mentions_scan_entity", "scan_id", "entity_id"),)


class ScanMetrics(Base):
    __tablename__ = "scan_metrics"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), primary_key=True
    )
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE")
    )
    job_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created_at()
