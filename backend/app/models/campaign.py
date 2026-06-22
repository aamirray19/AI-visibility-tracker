from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String, func
from sqlmodel import Field, SQLModel

from app.models.prompt import PromptStatus


class Campaign(SQLModel, table=True):
    __tablename__ = "campaign"
    __table_args__ = (
        Index("ix_campaign_owner_created_at", "owner_id", "created_at"),
        Index("ix_campaign_owner_id_id", "owner_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: str = Field(sa_column=Column(String(255), nullable=False))
    brand_name: str = Field(sa_column=Column(String(255), nullable=False))
    category: str = Field(sa_column=Column(String(255), nullable=False))
    prompt_count: int = Field(nullable=False, default=50)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


def derive_campaign_status(prompt_statuses: Sequence[PromptStatus]) -> str:
    if not prompt_statuses:
        return "CREATED"

    unique_statuses = set(prompt_statuses)

    if unique_statuses == {PromptStatus.PENDING}:
        return "CREATED"
    if PromptStatus.PROCESSING in unique_statuses:
        return "PROCESSING"
    if unique_statuses == {PromptStatus.COMPLETED}:
        return "COMPLETED"
    if unique_statuses == {PromptStatus.FAILED}:
        return "FAILED"
    if PromptStatus.PENDING in unique_statuses:
        return "PROCESSING"
    return "PARTIAL"
