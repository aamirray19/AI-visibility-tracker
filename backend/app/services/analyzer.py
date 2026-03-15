#Analyzer — judges AI responses for brand visibility using GPT-OSS-120B.
import json
import logging
import re
from groq import AsyncGroq
from app.core.config import settings

logger = logging.getLogger(__name__)


SYSTEM_ANALYSIS_PROMPT = """
You are an expert brand visibility analyst.

Your task is to analyze an AI-generated response and extract structured
information about brand mentions, competitors, sentiment, and cited sources.

You must return ONLY valid JSON following the exact schema below.

JSON Schema:

{
  "target_brand": {
    "is_mentioned": boolean,
    "rank": integer or null,
    "sentiment_score": float or null,
    "mention_context": "short quote from the text"
  },
  "competitors": [
    {
      "name": "Brand Name",
      "rank": integer or null,
      "sentiment_score": float or null
    }
  ],
  "cited_urls": [
    {
      "url": "https://example.com",
      "domain": "example.com",
      "is_target_brand": boolean
    }
  ]
}

Rules:

1. Target Brand Detection
- Set "is_mentioned" true only if the target brand appears in the text.
- Rank represents prominence in the response (1 = most prominent).
- If the brand is not mentioned, rank and sentiment_score must be null.

2. Competitor Detection
- Include only brands that appear in the response.
- Do not invent competitors.
- Each competitor must have:
  - name
  - rank (or null if unclear)
  - sentiment_score (or null)

3. Sentiment Score
- Range: 0.0 to 1.0
- 1.0 = very positive
- 0.5 = neutral
- 0.0 = very negative

4. Mention Context
- Provide a short quote or snippet where the brand appears.
- If not mentioned, return null.

5. URL Extraction
- Extract all URLs present in the text.
- Domain must match the hostname.
- Mark is_target_brand = true if the domain belongs to the target brand.

6. Output Rules
- Return ONLY valid JSON.
- Do NOT include markdown.
- Do NOT include explanations.
- Do NOT include extra text.
"""


USER_ANALYSIS_PROMPT = """
Target Brand: {brand_name}

AI Response:
---
{text_content}
---
"""


from typing import List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl, validator

class TargetBrandData(BaseModel):
    is_mentioned: bool
    rank: Optional[int] = Field(None, ge=1, le=10)
    sentiment_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    mention_context: Optional[str] = None

class CompetitorData(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    rank: Optional[int] = Field(None, ge=1, le=10)
    sentiment_score: Optional[float] = Field(None, ge=0.0, le=1.0)

class CitedUrlData(BaseModel):
    url: HttpUrl
    domain: str = Field(min_length=1, max_length=255)
    is_target_brand: bool

class AnalyzerResult(BaseModel):
    target_brand: TargetBrandData
    competitors: List[CompetitorData] = []
    cited_urls: List[CitedUrlData] = []


class Analyzer:
    def __init__(self):
        self._groq = AsyncGroq(api_key=settings.GROQ_API_KEY)

    async def analyze_result(self, text_content: str, brand_name: str) -> dict:
        logger.debug("Analyzing response for brand=%s (text_len=%d)", brand_name, len(text_content))

        try:
            response = await self._groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_ANALYSIS_PROMPT},
                    {"role": "user", "content": USER_ANALYSIS_PROMPT.format(
                        brand_name=brand_name,
                        text_content=text_content[:6000],
                    )},
                ],
                temperature=0.1,
                max_tokens=1500,
            )

            raw = response.choices[0].message.content or "{}"
            
            raw = raw.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                raw = raw.replace("json", "", 1).strip()

            parsed_data = AnalyzerResult.model_validate_json(raw).model_dump(mode="json")
            
            for c in parsed_data.get("cited_urls", []):
                if not isinstance(c.get("url"), str):
                     c["url"] = str(c["url"])

            logger.info(
                "Analysis done for brand=%s — mentioned=%s rank=%s",
                brand_name,
                parsed_data.get("target_brand", {}).get("is_mentioned"),
                parsed_data.get("target_brand", {}).get("rank"),
            )
            return parsed_data

        except Exception as e:
            logger.error("Analyzer API call or Validation failed for brand=%s: %s", brand_name, e, exc_info=True)
            return _empty_analysis()


def _empty_analysis() -> dict:
    """Safe fallback when analysis fails."""
    return AnalyzerResult(
        target_brand=TargetBrandData(
            is_mentioned=False,
            rank=None,
            sentiment_score=None,
            mention_context=None
        ),
        competitors=[],
        cited_urls=[]
    ).model_dump(mode="json")