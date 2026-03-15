from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime

def get_utc_now():
    return datetime.now(timezone.utc)

class CompetitorMention(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    result_id: int = Field(foreign_key="result.id", nullable=False)  
    brand_name: str = Field(nullable=False)  
    rank: Optional[int] = Field(default=None) 
    sentiment_score: Optional[float] = None 
    created_at: datetime = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
