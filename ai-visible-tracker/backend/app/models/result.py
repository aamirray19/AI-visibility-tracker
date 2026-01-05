from typing import Optional, Dict, Any
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Text, JSON
from datetime import datetime

class Result(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_id: Optional[int] = Field(default=None, foreign_key="prompt.id")
    
    # New Fields for API Pivot
    platform: str = Field(default="gemini") # e.g. "gemini", "chatgpt"
    response_text: str = Field(sa_column=Column(Text)) # The raw AI response
    
    # Analysis Fields
    rank: Optional[int] = Field(default=None) # e.g. 1 if brand is mentioned positively first? Concept is blurrier here.
    sentiment_score: Optional[float] = None
    analysis_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
