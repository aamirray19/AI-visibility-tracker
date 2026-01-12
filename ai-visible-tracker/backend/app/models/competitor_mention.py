from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class CompetitorMention(SQLModel, table=True):
    """
    Tracks competitor brands mentioned in AI responses.
    Used for Competitor Leaderboard.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    result_id: Optional[int] = Field(default=None, foreign_key="result.id")
    
    brand_name: str  
    rank: Optional[int] = Field(default=None) 
    sentiment_score: Optional[float] = None 
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
