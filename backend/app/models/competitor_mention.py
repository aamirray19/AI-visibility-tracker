from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func
from sqlmodel import Field, SQLModel


class CompetitorMention(SQLModel, table=True):
    __tablename__ = "competitor_mention"
    __table_args__ = (
        Index("ix_competitor_mention_result_id", "result_id"),
        Index("ix_competitor_mention_brand_name", "brand_name"),
    )

    id: int | None = Field(default=None, primary_key=True)
    result_id: int = Field(
        sa_column=Column(ForeignKey("result.id", ondelete="CASCADE"), nullable=False)
    )
    brand_name: str = Field(sa_column=Column(String(255), nullable=False))
    rank: int | None = Field(default=None, nullable=True)
    sentiment_score: float | None = Field(default=None, nullable=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
