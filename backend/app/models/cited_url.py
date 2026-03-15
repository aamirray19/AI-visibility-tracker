from typing import Optional
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Text, DateTime
from datetime import datetime, timezone

def get_utc_now():
    return datetime.now(timezone.utc)

class CitedUrl(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    result_id: int = Field(foreign_key="result.id", nullable=False)
    url: str = Field(sa_column=Column(Text, nullable=False))  
    domain: str = Field(default="unknown", nullable=False)  
    is_target_brand: bool = Field(default=False, nullable=False)  
    created_at: datetime = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
