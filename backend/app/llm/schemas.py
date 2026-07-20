from typing import Literal

from pydantic import BaseModel, Field


class EnrichmentProduct(BaseModel):
    name: str
    description: str | None = None


class EnrichmentCompetitor(BaseModel):
    name: str
    domain: str | None = None
    aliases: list[str] = []


class EnrichmentResult(BaseModel):
    industry: str | None = None
    description: str | None = None
    aliases: list[str] = []
    keywords: list[str] = []
    products: list[EnrichmentProduct] = []
    competitors: list[EnrichmentCompetitor] = []
    is_known: bool
    confidence: float = Field(ge=0.0, le=1.0)


class VerificationIssue(BaseModel):
    field: str  # which part of the profile this concerns, e.g. "competitors"
    value: str  # the specific flagged item
    reason: str


class VerificationResult(BaseModel):
    verdict: Literal["ok", "issues_found"]
    issues: list[VerificationIssue] = []


class GeneratedPrompt(BaseModel):
    text: str


class PromptGenerationResult(BaseModel):
    prompts: list[GeneratedPrompt]


class EvaluationResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    recommended: bool = False
    rank_position: int | None = None
    mentioned_companies: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning: str | None = None
