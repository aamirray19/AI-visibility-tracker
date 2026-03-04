from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from app.core.db import get_session
from app.models.campaign import Campaign, Prompt
from app.models.result import Result
from app.models.cited_url import CitedUrl
from app.models.competitor_mention import CompetitorMention
from app.services.llm import generate_brand_list
from app.services.prompt_factory import generate_campaign_prompts
from app.services.executor import SUPPORTED_PLATFORMS
from datetime import datetime, timedelta
from arq import create_pool
from app.core.queue import redis_settings
import os

router = APIRouter()

# --- Schemas ---
class CategoryRequest(BaseModel):
    category: str

class BrandListResponse(BaseModel):
    brands: List[str]

class CreateCampaignRequest(BaseModel):
    brand: str
    category: str

class CampaignResponse(BaseModel):
    id: int
    brand: str
    status: str
    prompt_count: int

# Advanced Dashboard Schemas
class AdvancedMetrics(BaseModel):
    ai_visibility: float          
    citation_share: float          
    share_of_voice: float          
    average_rank: float
    average_sentiment: float
    total_mentions: int
    total_citations: int

class CompetitorStats(BaseModel):
    name: str
    mention_count: int
    ai_visibility: float
    average_rank: float
    average_sentiment: float

class CitedPage(BaseModel):
    url: str
    domain: str
    mention_count: int
    is_target_brand: bool

class PromptResult(BaseModel):
    id: int
    text: str
    intent: str
    status: str 
    rank: Optional[int]
    sentiment: Optional[float]
    response_text: Optional[str]
    platform: Optional[str]

class EnhancedDashboardResponse(BaseModel):
    id: int
    brand: str
    total_prompts: int
    processed_count: int
    metrics: AdvancedMetrics
    competitors: List[CompetitorStats]
    top_cited_pages: List[CitedPage]
    mentioned_prompts: List[PromptResult] 
    results: List[PromptResult] 

# --- Endpoints ---

@router.post("/companies/discover", response_model=BrandListResponse)
async def discover_companies(request: CategoryRequest):
    try:
        brands = await generate_brand_list(request.category)
        return BrandListResponse(brands=brands)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/campaigns/create", response_model=CampaignResponse)
async def create_campaign(
    request: CreateCampaignRequest,
    session: AsyncSession = Depends(get_session)
):
    # 1. Generate Prompts
    prompts_data = await generate_campaign_prompts(request.brand, request.category)
    
    # 2. Save to DB
    new_campaign = Campaign(brand_name=request.brand, category=request.category)
    session.add(new_campaign)
    await session.commit()
    await session.refresh(new_campaign)
    
    created_prompts = []
    for p_data in prompts_data:
        # Handle both dict and string formats
        if isinstance(p_data, dict):
            text = p_data.get("text", "")
            intent = p_data.get("type", "commercial")
        else:
            # Fallback if it's a string
            text = str(p_data)
            intent = "commercial"
            
        prompt = Prompt(
            campaign_id=new_campaign.id,
            text=text,
            intent_type=intent
        )
        session.add(prompt)
        created_prompts.append(prompt)
    
    await session.commit()

    # 3. Enqueue Jobs
    try:
        redis = await create_pool(redis_settings)
        for p in created_prompts:
            await session.refresh(p)
            await redis.enqueue_job('process_prompt_job', p.id)
        await redis.close()
    except Exception as e:
        print(f"Failed to enqueue jobs: {e}")
    
    return CampaignResponse(
        id=new_campaign.id,
        brand=new_campaign.brand_name,
        status="CREATED",
        prompt_count=len(prompts_data)
    )

@router.get("/campaigns/{campaign_id}", response_model=EnhancedDashboardResponse)
async def get_campaign_dashboard(
    campaign_id: int,
    session: AsyncSession = Depends(get_session)
):
    # 1. Fetch campaign
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # 2. Fetch prompts
    statement = select(Prompt).where(Prompt.campaign_id == campaign_id)
    results = await session.exec(statement)
    prompts = results.all()
    
    # 3. Fetch all results for this campaign
    result_ids = []
    dashboard_results = []
    mentioned_prompts = []
    processed_count = 0
    total_rank = 0
    ranked_count = 0
    mentions_count = 0
    total_sentiment = 0
    sentiment_count = 0

    for prompt in prompts:
        r_stmt = select(Result).where(Result.prompt_id == prompt.id).order_by(Result.created_at.desc())
        r_res = await session.exec(r_stmt)
        prompt_results = r_res.all()
        prompt_results_by_platform = {r.platform: r for r in prompt_results}

        for platform in SUPPORTED_PLATFORMS:
            result = prompt_results_by_platform.get(platform)

            if result:
                result_ids.append(result.id)
                processed_count += 1
                p_res = PromptResult(
                    id=result.id,
                    text=prompt.text,
                    intent=prompt.intent_type,
                    status="COMPLETED",
                    rank=result.rank,
                    sentiment=result.sentiment_score,
                    response_text=result.response_text,
                    platform=result.platform
                )

                if result.rank and result.rank > 0:
                    total_rank += result.rank
                    ranked_count += 1
                    mentions_count += 1
                    mentioned_prompts.append(p_res)

                if result.sentiment_score is not None:
                    total_sentiment += result.sentiment_score
                    sentiment_count += 1
            else:
                p_res = PromptResult(
                    id=(prompt.id * 1000) + SUPPORTED_PLATFORMS.index(platform),
                    text=prompt.text,
                    intent=prompt.intent_type,
                    status="PENDING",
                    rank=None,
                    sentiment=None,
                    response_text=None,
                    platform=platform
                )

            dashboard_results.append(p_res)
    
    # Calculate basic metrics
    avg_rank = total_rank / ranked_count if ranked_count > 0 else 0
    expected_results = len(prompts) * len(SUPPORTED_PLATFORMS)
    ai_visibility = (mentions_count / expected_results) * 100 if expected_results else 0
    avg_sentiment = total_sentiment / sentiment_count if sentiment_count > 0 else 0
    
    # Calculate Citation Share
    if result_ids:  # Safety check: avoid SQL error with empty list
        citation_query = select(func.count(func.distinct(CitedUrl.result_id))).where(
            CitedUrl.result_id.in_(result_ids),
            CitedUrl.is_target_brand == True
        )
        citation_result = await session.exec(citation_query)
        citation_count = citation_result.one()
    else:
        citation_count = 0
    
    citation_share = (citation_count / expected_results) * 100 if expected_results else 0
    
    # Get Competitor Stats
    competitor_stats_dict = {}
    if result_ids:  # Safety check: avoid SQL error with empty list
        competitor_query = select(CompetitorMention).where(
            CompetitorMention.result_id.in_(result_ids)
        )
        competitor_mentions = await session.exec(competitor_query)
        
        # Aggregate competitors
        for cm in competitor_mentions.all():
            if cm.brand_name not in competitor_stats_dict:
                competitor_stats_dict[cm.brand_name] = {
                    "count": 0,
                    "ranks": [],
                    "sentiments": []
                }
            competitor_stats_dict[cm.brand_name]["count"] += 1
            if cm.rank:
                competitor_stats_dict[cm.brand_name]["ranks"].append(cm.rank)
            if cm.sentiment_score is not None:
                competitor_stats_dict[cm.brand_name]["sentiments"].append(cm.sentiment_score)
    
    # Build competitor list
    competitors = []
    for brand, stats in competitor_stats_dict.items():
        avg_comp_rank = sum(stats["ranks"]) / len(stats["ranks"]) if stats["ranks"] else 0
        avg_comp_sentiment = sum(stats["sentiments"]) / len(stats["sentiments"]) if stats["sentiments"] else 0
        comp_visibility = (stats["count"] / expected_results) * 100 if expected_results else 0
        
        competitors.append(CompetitorStats(
            name=brand,
            mention_count=stats["count"],
            ai_visibility=comp_visibility,
            average_rank=avg_comp_rank,
            average_sentiment=avg_comp_sentiment
        ))
    
    # Sort by visibility
    competitors.sort(key=lambda x: x.ai_visibility, reverse=True)
    
    # Get Top Cited Pages
    top_cited_pages = []
    if result_ids:  # Safety check: avoid SQL error with empty list
        url_query = select(
            CitedUrl.url,
            CitedUrl.domain,
            CitedUrl.is_target_brand,
            func.count(CitedUrl.id).label("count")
        ).where(
            CitedUrl.result_id.in_(result_ids)
        ).group_by(
            CitedUrl.url,
            CitedUrl.domain,
            CitedUrl.is_target_brand
        ).order_by(
            func.count(CitedUrl.id).desc()
        ).limit(10)
        
        top_urls_result = await session.exec(url_query)
        top_cited_pages = [
            CitedPage(
                url=row[0],
                domain=row[1],
                is_target_brand=row[2],
                mention_count=row[3]
            )
            for row in top_urls_result.all()
        ]
    
    # Build response
    metrics = AdvancedMetrics(
        ai_visibility=ai_visibility,
        citation_share=citation_share,
        share_of_voice=ai_visibility,  # Same metric
        average_rank=avg_rank,
        average_sentiment=avg_sentiment,
        total_mentions=mentions_count,
        total_citations=citation_count
    )
    
    return EnhancedDashboardResponse(
        id=campaign.id,
        brand=campaign.brand_name,
        total_prompts=expected_results,
        processed_count=processed_count,
        metrics=metrics,
        competitors=competitors,
        top_cited_pages=top_cited_pages,
        mentioned_prompts=mentioned_prompts,
        results=dashboard_results
    )
