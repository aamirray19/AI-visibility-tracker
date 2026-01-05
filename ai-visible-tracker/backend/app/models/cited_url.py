from typing import Optional
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Text
from datetime import datetime

class CitedUrl(SQLModel, table=True):
    """
    Tracks URLs/citations found in AI responses.
    Used to calculate Citation Share metric.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    result_id: Optional[int] = Field(default=None, foreign_key="result.id")
    
    url: str = Field(sa_column=Column(Text))  # Full URL
    domain: str = Field(default="unknown")  # Extracted domain with safe default
    is_target_brand: bool = Field(default=False)  # Does this URL belong to target brand?
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
