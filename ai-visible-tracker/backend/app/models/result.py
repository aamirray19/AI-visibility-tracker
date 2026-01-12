from typing import Optional, Dict, Any
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Text, JSON
from datetime import datetime

class Result(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_id: Optional[int] = Field(default=None, foreign_key="prompt.id")
    platform: str = Field(default="groq") 
    response_text: str = Field(sa_column=Column(Text)) 
    rank: Optional[int] = Field(default=None) 
    sentiment_score: Optional[float] = None
    analysis_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
