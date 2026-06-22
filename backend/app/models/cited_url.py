from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, func
from sqlmodel import Field, SQLModel


class CitedUrl(SQLModel, table=True):
    __tablename__ = "cited_url"
    __table_args__ = (
        Index("ix_cited_url_result_id", "result_id"),
        Index("ix_cited_url_domain", "domain"),
        Index("ix_cited_url_is_target_brand", "is_target_brand"),
    )

    id: int | None = Field(default=None, primary_key=True)
    result_id: int = Field(
        sa_column=Column(ForeignKey("result.id", ondelete="CASCADE"), nullable=False)
    )
    url: str = Field(sa_column=Column(String, nullable=False))
    domain: str = Field(sa_column=Column(String(255), nullable=False))
    title: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    source_provider: str = Field(sa_column=Column(String(100), nullable=False))
    is_target_brand: bool = Field(default=False, nullable=False)
    citation_type: str = Field(sa_column=Column(String(100), nullable=False))
    metadata_json: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
