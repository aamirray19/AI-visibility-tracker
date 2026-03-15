from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime


def get_utc_now():
    return datetime.now(timezone.utc)


class Campaign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    brand_name: str
    category: str
    created_at: datetime = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))

    prompts: List["Prompt"] = Relationship(back_populates="campaign")


class Prompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id", nullable=False)
    text: str
    intent_type: str = Field(default="commercial", nullable=False)
    status: str = Field(default="PENDING", nullable=False)
    created_at: datetime = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))

    campaign: Optional[Campaign] = Relationship(back_populates="prompts")
