from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, DateTime, Enum as SqlEnum, ForeignKey, Index, String, func
from sqlmodel import Field, SQLModel


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Result(SQLModel, table=True):
    __tablename__ = "result"
    __table_args__ = (
        Index("ix_result_prompt_provider", "prompt_id", "provider"),
        Index("ix_result_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    prompt_id: int = Field(
        sa_column=Column(ForeignKey("prompt.id", ondelete="CASCADE"), nullable=False)
    )
    provider: str = Field(sa_column=Column(String(100), nullable=False))
    model: str = Field(sa_column=Column(String(255), nullable=False))
    response_text: str = Field(sa_column=Column(String, nullable=False))
    brand_mentioned: bool | None = Field(default=None, nullable=True)
    rank: int | None = Field(default=None, nullable=True)
    sentiment_score: float | None = Field(default=None, nullable=True)
    mention_context: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    analysis_status: AnalysisStatus = Field(
        sa_column=Column(
            SqlEnum(AnalysisStatus, name="analysis_status"),
            nullable=False,
            server_default=AnalysisStatus.PENDING.value,
        )
    )
    provider_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
