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
    
    brand_name: str  # Name of competitor brand
    rank: Optional[int] = Field(default=None)  # Position in response (1=first, 2=second, etc.)
    sentiment_score: Optional[float] = None  # 0.0 to 1.0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
