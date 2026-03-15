import json
import logging
from typing import List, Optional, Dict, Annotated
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, StringConstraints
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from arq import create_pool
from app.core.db import get_session
from app.core.config import settings
from app.core.queue import redis_settings
from app.models.campaign import Campaign, Prompt
from app.models.result import Result
from app.models.cited_url import CitedUrl
from app.models.competitor_mention import CompetitorMention
from app.services.llm import generate_brand_list
from app.services.prompt_factory import generate_campaign_prompts
from app.core.limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


#Request / Response Schemas

class CategoryRequest(BaseModel):
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class BrandListResponse(BaseModel):
    brands: List[str]


class CreateCampaignRequest(BaseModel):
    brand: Annotated[
        str, 
        StringConstraints(
            strip_whitespace=True, 
            min_length=1, 
            max_length=100, 
            pattern=r"^[\w\s\-\.\&\,\']+$"
        )
    ]
    category: Annotated[
        str, 
        StringConstraints(
            strip_whitespace=True, 
            min_length=1, 
            max_length=150
        )
    ]


class CampaignResponse(BaseModel):
    id: int
    brand: str
    status: str
    prompt_count: int


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


class ModelMetrics(BaseModel):
    platform: str
    ai_visibility: float
    average_rank: float
    average_sentiment: float
    total_mentions: int
    total_results: int


class PromptResult(BaseModel):
    id: int
    text: str
    intent: str
    status: str
    rank: Optional[int]
    sentiment: Optional[float]
    response_text: Optional[str]
    platform: Optional[str]


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_results: int
    total_pages: int


class EnhancedDashboardResponse(BaseModel):
    id: int
    brand: str
    total_prompts: int
    processed_count: int
    is_complete: bool
    metrics: AdvancedMetrics
    per_model_metrics: List[ModelMetrics]
    competitors: List[CompetitorStats]
    top_cited_pages: List[CitedPage]
    mentioned_prompts: List[PromptResult]
    results: List[PromptResult]
    pagination: PaginationMeta


#Helper: Redis cache client

async def _get_redis():
    """Returns a raw redis client for caching (separate from ARQ pool)."""
    import redis.asyncio as aioredis
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


#Endpoints

@router.post("/companies/discover", response_model=BrandListResponse)
@limiter.limit("10/minute")
async def discover_companies(request: Request, body: CategoryRequest):
    try:
        brands = await generate_brand_list(body.category)
        return BrandListResponse(brands=brands)
    except Exception as e:
        logger.error("discover_companies failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/create", response_model=CampaignResponse)
@limiter.limit("5/minute")
async def create_campaign(
    request: Request,
    body: CreateCampaignRequest,
    session: AsyncSession = Depends(get_session),
):
    logger.info("Creating campaign: brand=%s category=%s", body.brand, body.category)

    prompts_data = await generate_campaign_prompts(body.brand, body.category)

    new_campaign = Campaign(brand_name=body.brand, category=body.category)
    session.add(new_campaign)
    await session.flush() 

    created_prompts = []
    for p_data in prompts_data:
        if isinstance(p_data, dict):
            text = p_data.get("text", "")
            intent = p_data.get("type", "commercial")
        else:
            text = str(p_data)
            intent = "commercial"

        prompt = Prompt(campaign_id=new_campaign.id, text=text, intent_type=intent)
        session.add(prompt)
        created_prompts.append(prompt)

    await session.flush() 
    
    try:
        redis = await create_pool(redis_settings)
        for p in created_prompts:
            await redis.enqueue_job("process_prompt_job", p.id)
        await redis.close()
        logger.info("Enqueued %d jobs for campaign %d", len(created_prompts), new_campaign.id)
        

        await session.commit()
    except Exception as e:
        logger.error("Failed to enqueue jobs for campaign %d: %s", new_campaign.id, e)
        await session.rollback()
        raise HTTPException(
            status_code=503, 
            detail="Service momentarily unavailable (queue failure). Please try again."
        )

    return CampaignResponse(
        id=new_campaign.id,
        brand=new_campaign.brand_name,
        status="CREATED",
        prompt_count=len(prompts_data),
    )


@router.get("/campaigns/{campaign_id}", response_model=EnhancedDashboardResponse)
@limiter.limit("60/minute")
async def get_campaign_dashboard(
    request: Request,
    campaign_id: int,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=200, description="Results per page"),
    session: AsyncSession = Depends(get_session),
):


    redis = await _get_redis()
    cache_key = f"dashboard:{campaign_id}:p{page}:ps{page_size}"

    try:
        cached = await redis.get(cache_key)
        if cached:
            logger.debug("Cache hit for campaign %d", campaign_id)
            return EnhancedDashboardResponse(**json.loads(cached))
    except Exception as e:
        logger.warning("Redis cache read failed: %s", e)
    finally:
        await redis.aclose()


    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    prompts_stmt = select(Prompt).where(Prompt.campaign_id == campaign_id)
    prompts = (await session.exec(prompts_stmt)).all()
    total_prompts = len(prompts)

    if total_prompts == 0:
        return _empty_dashboard(campaign, page, page_size)

    prompt_ids = [p.id for p in prompts]
    prompt_map: Dict[int, Prompt] = {p.id: p for p in prompts}


    results_stmt = (
        select(Result)
        .where(Result.prompt_id.in_(prompt_ids))
        .order_by(Result.created_at.desc())
    )
    all_results = (await session.exec(results_stmt)).all()


    latest_by_key: Dict[tuple, Result] = {}
    for r in all_results:
        key = (r.prompt_id, r.platform)
        if key not in latest_by_key:
            latest_by_key[key] = r

    result_ids = [r.id for r in latest_by_key.values()]

    results_by_prompt: Dict[int, list[Result]] = {}
    for r in latest_by_key.values():
        results_by_prompt.setdefault(r.prompt_id, []).append(r)

    total_rank = 0
    ranked_count = 0
    mentions_count = 0
    total_sentiment = 0.0
    sentiment_count = 0
    processed_prompt_ids: set[int] = set()
    model_stats: Dict[str, dict] = {}

    mentioned_prompts: List[PromptResult] = []
    
    all_individual_results: List[PromptResult] = []

    for prompt in prompts:
        prompt_results = results_by_prompt.get(prompt.id, [])
        has_result = bool(prompt_results)
        if has_result:
            processed_prompt_ids.add(prompt.id)

        representative = prompt_results[0] if prompt_results else None
        if representative and representative.rank and representative.rank > 0:
            p_res = PromptResult(
                id=prompt.id, 
                text=prompt.text,
                intent=prompt.intent_type,
                status=prompt.status,
                rank=representative.rank if representative else None,
                sentiment=representative.sentiment_score if representative else None,
                response_text=representative.response_text if representative else None,
                platform=representative.platform if representative else None,
            )
            mentioned_prompts.append(p_res)

        for result in prompt_results:
            platform = result.platform

            ind_res = PromptResult(
                id=result.id, 
                text=prompt.text,
                intent=prompt.intent_type,
                status=prompt.status,
                rank=result.rank,
                sentiment=result.sentiment_score,
                response_text=result.response_text,
                platform=result.platform,
            )
            all_individual_results.append(ind_res)

            if result.rank and result.rank > 0:
                total_rank += result.rank
                ranked_count += 1
                mentions_count += 1

            if result.sentiment_score is not None:
                total_sentiment += result.sentiment_score
                sentiment_count += 1

            if platform not in model_stats:
                model_stats[platform] = {"ranks": [], "sentiments": [], "mentions": 0, "total": 0}
            model_stats[platform]["total"] += 1
            if result.rank and result.rank > 0:
                model_stats[platform]["ranks"].append(result.rank)
                model_stats[platform]["mentions"] += 1
            if result.sentiment_score is not None:
                model_stats[platform]["sentiments"].append(result.sentiment_score)


    processed_count = len(processed_prompt_ids)
    avg_rank = total_rank / ranked_count if ranked_count > 0 else 0.0
    ai_visibility = (mentions_count / total_prompts) * 100 if total_prompts else 0.0
    avg_sentiment = total_sentiment / sentiment_count if sentiment_count > 0 else 0.0


    citation_count = 0
    if result_ids:
        citation_q = select(func.count(func.distinct(CitedUrl.result_id))).where(
            CitedUrl.result_id.in_(result_ids),
            CitedUrl.is_target_brand == True,
        )
        citation_count = (await session.exec(citation_q)).one() or 0

    citation_share = (citation_count / total_prompts) * 100 if total_prompts else 0.0


    per_model_metrics = [
        ModelMetrics(
            platform=platform,
            ai_visibility=(stats["mentions"] / total_prompts) * 100 if total_prompts else 0.0,
            average_rank=sum(stats["ranks"]) / len(stats["ranks"]) if stats["ranks"] else 0.0,
            average_sentiment=sum(stats["sentiments"]) / len(stats["sentiments"]) if stats["sentiments"] else 0.0,
            total_mentions=stats["mentions"],
            total_results=stats["total"],
        )
        for platform, stats in model_stats.items()
    ]


    competitor_stats_dict: Dict[str, dict] = {}
    if result_ids:
        comp_q = select(CompetitorMention).where(CompetitorMention.result_id.in_(result_ids))
        for cm in (await session.exec(comp_q)).all():
            d = competitor_stats_dict.setdefault(cm.brand_name, {"count": 0, "ranks": [], "sentiments": []})
            d["count"] += 1
            if cm.rank:
                d["ranks"].append(cm.rank)
            if cm.sentiment_score is not None:
                d["sentiments"].append(cm.sentiment_score)

    competitors = sorted(
        [
            CompetitorStats(
                name=brand,
                mention_count=s["count"],
                ai_visibility=(s["count"] / total_prompts) * 100,
                average_rank=sum(s["ranks"]) / len(s["ranks"]) if s["ranks"] else 0.0,
                average_sentiment=sum(s["sentiments"]) / len(s["sentiments"]) if s["sentiments"] else 0.0,
            )
            for brand, s in competitor_stats_dict.items()
        ],
        key=lambda x: x.ai_visibility,
        reverse=True,
    )

    top_cited_pages: List[CitedPage] = []
    if result_ids:
        url_q = (
            select(CitedUrl.url, CitedUrl.domain, CitedUrl.is_target_brand, func.count(CitedUrl.id).label("cnt"))
            .where(CitedUrl.result_id.in_(result_ids))
            .group_by(CitedUrl.url, CitedUrl.domain, CitedUrl.is_target_brand)
            .order_by(func.count(CitedUrl.id).desc())
            .limit(10)
        )
        top_cited_pages = [
            CitedPage(url=row[0], domain=row[1], is_target_brand=row[2], mention_count=row[3])
            for row in (await session.exec(url_q)).all()
        ]

    all_individual_results.sort(key=lambda x: x.id, reverse=True) 
    
    total_result_count = len(all_individual_results)
    total_pages = max(1, (total_result_count + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size
    paginated_results = all_individual_results[offset: offset + page_size]

    is_complete = processed_count >= total_prompts and total_prompts > 0

    metrics = AdvancedMetrics(
        ai_visibility=ai_visibility,
        citation_share=citation_share,
        share_of_voice=ai_visibility,
        average_rank=avg_rank,
        average_sentiment=avg_sentiment,
        total_mentions=mentions_count,
        total_citations=citation_count,
    )

    response = EnhancedDashboardResponse(
        id=campaign.id,
        brand=campaign.brand_name,
        total_prompts=total_prompts,
        processed_count=processed_count,
        is_complete=is_complete,
        metrics=metrics,
        per_model_metrics=per_model_metrics,
        competitors=competitors,
        top_cited_pages=top_cited_pages,
        mentioned_prompts=mentioned_prompts,
        results=paginated_results,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_results=total_result_count,
            total_pages=total_pages,
        ),
    )

    if is_complete:
        try:
            redis_w = await _get_redis()
            await redis_w.setex(cache_key, settings.DASHBOARD_CACHE_TTL_SECONDS, response.model_dump_json())
            await redis_w.aclose()
            logger.info("Cached completed dashboard for campaign %d", campaign_id)
        except Exception as e:
            logger.warning("Redis cache write failed: %s", e)

    return response


def _empty_dashboard(campaign: Campaign, page: int, page_size: int) -> EnhancedDashboardResponse:
    """Returns a safe empty dashboard when a campaign has no prompts yet."""
    return EnhancedDashboardResponse(
        id=campaign.id,
        brand=campaign.brand_name,
        total_prompts=0,
        processed_count=0,
        is_complete=False,
        metrics=AdvancedMetrics(
            ai_visibility=0, citation_share=0, share_of_voice=0,
            average_rank=0, average_sentiment=0, total_mentions=0, total_citations=0,
        ),
        per_model_metrics=[],
        competitors=[],
        top_cited_pages=[],
        mentioned_prompts=[],
        results=[],
        pagination=PaginationMeta(page=1, page_size=page_size, total_results=0, total_pages=1),
    )
