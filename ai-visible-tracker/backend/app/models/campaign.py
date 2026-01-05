from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime

class Campaign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    brand_name: str
    category: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    prompts: List["Prompt"] = Relationship(back_populates="campaign")

class Prompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: Optional[int] = Field(default=None, foreign_key="campaign.id")
    text: str
    intent_type: str  # commercial | informational
    
    campaign: Optional[Campaign] = Relationship(back_populates="prompts")
