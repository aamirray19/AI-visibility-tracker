import base64
import uuid
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import INVALID_STATE_TRANSITION
from app.core.errors import AppError
from app.core.lifecycle import TRANSITIONS, transition
from app.db.models import AIResponse, Scan
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.scans import ScanRepository
from app.deps import get_arq_redis, get_db, get_redis, require_api_key
from app.services.onboarding import get_or_create_scan, resolve_company
from app.worker.queues import INTERACTIVE_QUEUE, PIPELINE_QUEUE

RETRYABLE_SCAN_STATUSES = ("failed", "completed_with_gaps")

router = APIRouter(prefix="/scans", tags=["scans"], dependencies=[Depends(require_api_key)])

CANCEL_FLAG_TTL_S = 3600


class MonitoringCategory(str, Enum):
    """The 9 fixed PRD Phase 4 categories. Guidance text into prompt
    generation (§7.4), not a filter -- see Phase 7."""

    BRAND_MENTIONS = "brand_mentions"
    PRODUCT_RECOMMENDATIONS = "product_recommendations"
    COMPETITOR_COMPARISONS = "competitor_comparisons"
    PURCHASE_INTENT = "purchase_intent"
    FEATURE_COMPARISONS = "feature_comparisons"
    ALTERNATIVES = "alternatives"
    REVIEWS = "reviews"
    PRICING_DISCUSSIONS = "pricing_discussions"
    TECHNICAL_EVALUATIONS = "technical_evaluations"


class CreateScanRequest(BaseModel):
    name: str
    website: str


class ScanResponse(BaseModel):
    id: str
    company_id: str
    status: str
    reused: bool = False
    monitoring_categories: list[str] = []

    @classmethod
    def from_scan(cls, scan: Scan, reused: bool = False) -> "ScanResponse":
        return cls(
            id=str(scan.id),
            company_id=str(scan.company_id),
            status=scan.status,
            reused=reused,
            monitoring_categories=scan.monitoring_categories,
        )


class ScopeRequest(BaseModel):
    categories: list[MonitoringCategory] | None = None


class ScanListResponse(BaseModel):
    items: list[ScanResponse]
    next_cursor: str | None = None


async def _get_or_404(scans: ScanRepository, scan_id: uuid.UUID) -> Scan:
    scan = await scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    return scan


def _encode_cursor(scan: Scan) -> str:
    raw = f"{scan.created_at.isoformat()}|{scan.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    created_at_str, id_str = raw.split("|")
    return datetime.fromisoformat(created_at_str), uuid.UUID(id_str)


@router.post("", status_code=202, response_model=ScanResponse)
async def create_scan(
    body: CreateScanRequest,
    force: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    arq_redis=Depends(get_arq_redis),
) -> ScanResponse:
    """Creates/reuses the scan row (§7.1) and kicks off Phase 5-8's pipeline
    entry point. `reused=True` (a completed scan from the recent-scan cache)
    skips the enqueue; everything else does not need to distinguish "brand
    new" from "still-active" -- the deterministic `_job_id` makes a redundant
    enqueue call a safe no-op (§8), and `lifecycle.transition()` inside the
    job itself rejects re-running it on a scan that's already past that
    stage."""
    company = await resolve_company(session, redis, body.name, body.website)
    scan, reused = await get_or_create_scan(session, redis, company, force=force)
    await session.commit()
    if not reused:
        await arq_redis.enqueue_job(
            "enrich_company",
            str(scan.id),
            _job_id=f"enrich:{scan.id}",
            _queue_name=INTERACTIVE_QUEUE,
        )
    return ScanResponse.from_scan(scan, reused=reused)


@router.get("", response_model=ScanListResponse)
async def list_scans(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_db),
) -> ScanListResponse:
    stmt = select(Scan).order_by(Scan.created_at.desc(), Scan.id.desc()).limit(limit + 1)
    if cursor:
        created_at, scan_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (Scan.created_at < created_at) | ((Scan.created_at == created_at) & (Scan.id < scan_id))
        )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    next_cursor = _encode_cursor(rows[limit]) if len(rows) > limit else None
    return ScanListResponse(items=[ScanResponse.from_scan(s) for s in rows[:limit]], next_cursor=next_cursor)


@router.get("/{scan_id}")
async def get_scan(
    scan_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    scans = ScanRepository(session)
    scan = await _get_or_404(scans, scan_id)
    progress = await redis.hgetall(f"scan:{scan_id}:progress")
    company = await CompanyRepository(session).get(scan.company_id)
    return {
        **ScanResponse.from_scan(scan).model_dump(),
        "progress": progress,
        "company_name": company.name if company else None,
        "company_domain": company.domain if company else None,
    }


@router.post("/{scan_id}/launch", status_code=202, response_model=ScanResponse)
async def launch_scan(
    scan_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    arq_redis=Depends(get_arq_redis),
) -> ScanResponse:
    """§7.5/§8: starts Phases 5-8. `409` unless `scope_pending`."""
    scans = ScanRepository(session)
    scan = await _get_or_404(scans, scan_id)
    transition(scan, "queued")
    await session.commit()
    await arq_redis.enqueue_job(
        "generate_prompts",
        str(scan_id),
        _job_id=f"generate_prompts:{scan_id}",
        _queue_name=PIPELINE_QUEUE,
    )
    return ScanResponse.from_scan(scan)


@router.delete("/{scan_id}", status_code=204)
async def cancel_scan(
    scan_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> None:
    """Always sets the cooperative-cancellation flag jobs check between steps.
    Also flips `status` immediately when cancelled is a legal transition from
    where the scan currently sits (§5) -- otherwise the in-flight job notices
    the flag and terminates on its own next step."""
    scans = ScanRepository(session)
    scan = await _get_or_404(scans, scan_id)
    await redis.setex(f"scan:{scan_id}:cancelled", CANCEL_FLAG_TTL_S, "1")
    if "cancelled" in TRANSITIONS.get(scan.status, set()):
        transition(scan, "cancelled")
        await session.commit()


@router.put("/{scan_id}/scope", response_model=ScanResponse)
async def set_scope(
    scan_id: uuid.UUID,
    body: ScopeRequest,
    session: AsyncSession = Depends(get_db),
) -> ScanResponse:
    """§7.4: stores the monitoring scope. Unknown category values are
    rejected by Pydantic's enum validation (a plain 422) before this body
    even runs -- no custom error code needed for that, only for the
    state-machine guard below."""
    scans = ScanRepository(session)
    scan = await _get_or_404(scans, scan_id)
    if scan.status != "scope_pending":
        raise AppError(
            INVALID_STATE_TRANSITION,
            f"Cannot set scope while scan is '{scan.status}'",
            status_code=409,
            details={"from": scan.status},
        )

    categories = body.categories or list(MonitoringCategory)
    scan.monitoring_categories = [c.value for c in categories]
    await session.commit()
    return ScanResponse.from_scan(scan)


@router.post("/{scan_id}/retry", status_code=202, response_model=ScanResponse)
async def retry_scan(
    scan_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    arq_redis=Depends(get_arq_redis),
) -> ScanResponse:
    """§13.2: re-runs only the failed/skipped ai_responses rows for a scan
    that didn't complete cleanly. Safe under a double-click because
    execute_prompt's own upsert on (prompt_id, provider) makes a rerun
    idempotent -- not because of job-id dedup, so the deterministic id here
    is just consistency, not the safety mechanism."""
    scans = ScanRepository(session)
    scan = await _get_or_404(scans, scan_id)
    if scan.status not in RETRYABLE_SCAN_STATUSES:
        raise AppError(
            INVALID_STATE_TRANSITION,
            f"Cannot retry a scan that is '{scan.status}'",
            status_code=409,
            details={"from": scan.status},
        )

    result = await session.execute(
        select(AIResponse).where(AIResponse.scan_id == scan_id, AIResponse.status.in_(["failed", "skipped"]))
    )
    to_retry = list(result.scalars().all())

    # reset the counters to this retry batch size so aggregate_scan's
    # early-fire guard waits for exactly this round
    await redis.set(f"scan:{scan_id}:pending_exec", len(to_retry), ex=3600)
    await redis.set(f"scan:{scan_id}:pending_eval", len(to_retry), ex=3600)
    for response in to_retry:
        await arq_redis.enqueue_job(
            "execute_prompt",
            str(scan_id),
            str(response.prompt_id),
            response.provider,
            _job_id=f"exec:{response.prompt_id}:{response.provider}",
            _queue_name=PIPELINE_QUEUE,
        )

    scan.status = "executing"
    await session.commit()
    return ScanResponse.from_scan(scan)
