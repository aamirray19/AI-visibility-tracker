from typing import Optional, Dict, Any
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Text, JSON, DateTime
from datetime import datetime, timezone

def get_utc_now():
    return datetime.now(timezone.utc)

class Result(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_id: int = Field(foreign_key="prompt.id", nullable=False)
    platform: str = Field(default="gpt", nullable=False) 
    response_text: str = Field(sa_column=Column(Text, nullable=False)) 
    brand_mentioned: bool = Field(default=False, nullable=False)
    rank: Optional[int] = Field(default=None) 
    sentiment_score: Optional[float] = None
    mention_context: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
