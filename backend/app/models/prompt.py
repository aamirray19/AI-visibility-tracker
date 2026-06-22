from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, Enum as SqlEnum, ForeignKey, Index, String, func
from sqlmodel import Field, SQLModel


class PromptIntentType(StrEnum):
    COMMERCIAL = "commercial"
    INFORMATIONAL = "informational"


class PromptStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class Prompt(SQLModel, table=True):
    __tablename__ = "prompt"
    __table_args__ = (
        Index("ix_prompt_campaign_status", "campaign_id", "status"),
        Index("ix_prompt_campaign_created_at", "campaign_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        sa_column=Column(ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False)
    )
    text: str = Field(sa_column=Column(String, nullable=False))
    intent_type: PromptIntentType = Field(
        sa_column=Column(
            SqlEnum(PromptIntentType, name="prompt_intent_type"),
            nullable=False,
        )
    )
    status: PromptStatus = Field(
        sa_column=Column(
            SqlEnum(PromptStatus, name="prompt_status"),
            nullable=False,
            server_default=PromptStatus.PENDING.value,
        )
    )
    error_message: str | None = Field(default=None, sa_column=Column(String, nullable=True))
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
