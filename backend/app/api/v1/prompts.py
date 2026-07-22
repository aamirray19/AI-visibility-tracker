import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIResponse, Evaluation, Prompt
from app.deps import get_db, require_api_key

router = APIRouter(prefix="/scans", tags=["prompts"], dependencies=[Depends(require_api_key)])


def _response_summary(response: AIResponse, evaluation: Evaluation | None) -> dict:
    return {
        "status": response.status,
        "target_mentioned": evaluation.target_mentioned if evaluation else None,
        "sentiment": evaluation.sentiment if evaluation else None,
        "recommended": evaluation.recommended if evaluation else None,
        "rank_position": evaluation.rank_position if evaluation else None,
    }


def _response_detail(response: AIResponse, evaluation: Evaluation | None) -> dict:
    return {
        "provider": response.provider,
        "model": response.model,
        "status": response.status,
        "raw_response": response.raw_response,
        "citations": response.citations,
        "evaluation": (
            {
                "sentiment": evaluation.sentiment,
                "target_mentioned": evaluation.target_mentioned,
                "recommended": evaluation.recommended,
                "rank_position": evaluation.rank_position,
                "mentioned_companies": evaluation.mentioned_companies,
                "confidence": float(evaluation.confidence) if evaluation.confidence is not None else None,
                "reasoning": evaluation.reasoning,
            }
            if evaluation
            else None
        ),
    }


@router.get("/{scan_id}/prompts")
async def list_prompts(
    scan_id: uuid.UUID,
    category: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    mentioned: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """§6 Prompt Explorer. Filters apply to a single joined (prompt,
    response, evaluation) row so "provider=groq&sentiment=positive" means
    "groq's response was positive", not "some provider was positive and
    groq has any response"."""
    match_stmt = (
        select(Prompt.id)
        .join(AIResponse, AIResponse.prompt_id == Prompt.id)
        .outerjoin(Evaluation, Evaluation.response_id == AIResponse.id)
        .where(Prompt.scan_id == scan_id)
        .distinct()
    )
    if category:
        match_stmt = match_stmt.where(Prompt.category == category)
    if provider:
        match_stmt = match_stmt.where(AIResponse.provider == provider)
    if sentiment:
        match_stmt = match_stmt.where(Evaluation.sentiment == sentiment)
    if mentioned is not None:
        match_stmt = match_stmt.where(Evaluation.target_mentioned == mentioned)

    matched_ids = (await session.execute(match_stmt)).scalars().all()
    total = len(matched_ids)

    prompts_stmt = (
        select(Prompt)
        .where(Prompt.id.in_(matched_ids))
        .order_by(Prompt.created_at)
        .offset(offset)
        .limit(limit)
    )
    page_prompts = (await session.execute(prompts_stmt)).scalars().all()

    items = []
    for prompt in page_prompts:
        rows = (
            await session.execute(
                select(AIResponse, Evaluation)
                .outerjoin(Evaluation, Evaluation.response_id == AIResponse.id)
                .where(AIResponse.prompt_id == prompt.id)
            )
        ).all()
        items.append(
            {
                "id": str(prompt.id),
                "text": prompt.text,
                "category": prompt.category,
                "target": prompt.target,
                "providers": {r.provider: _response_summary(r, ev) for r, ev in rows},
            }
        )

    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{scan_id}/prompts/{prompt_id}")
async def get_prompt_detail(scan_id: uuid.UUID, prompt_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> dict:
    """§6: both providers' responses + evaluations + citations for one prompt."""
    prompt = (
        await session.execute(select(Prompt).where(Prompt.id == prompt_id, Prompt.scan_id == scan_id))
    ).scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="prompt not found")

    rows = (
        await session.execute(
            select(AIResponse, Evaluation)
            .outerjoin(Evaluation, Evaluation.response_id == AIResponse.id)
            .where(AIResponse.prompt_id == prompt.id)
        )
    ).all()

    return {
        "id": str(prompt.id),
        "text": prompt.text,
        "category": prompt.category,
        "target": prompt.target,
        "responses": [_response_detail(r, ev) for r, ev in rows],
    }
