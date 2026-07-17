import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lifecycle import TRANSITIONS, transition
from app.db.models import Scan
from app.db.repositories.scans import ScanRepository
from app.deps import get_db, get_redis, require_api_key
from app.services.onboarding import get_or_create_scan, resolve_company

router = APIRouter(prefix="/scans", tags=["scans"], dependencies=[Depends(require_api_key)])

CANCEL_FLAG_TTL_S = 3600


class CreateScanRequest(BaseModel):
    name: str
    website: str


class ScanResponse(BaseModel):
    id: str
    company_id: str
    status: str
    reused: bool = False

    @classmethod
    def from_scan(cls, scan: Scan, reused: bool = False) -> "ScanResponse":
        return cls(id=str(scan.id), company_id=str(scan.company_id), status=scan.status, reused=reused)


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
) -> ScanResponse:
    """Creates/reuses the scan row only (§7.1). The `enrich_company` enqueue
    lands in Phase 4 once that job exists."""
    company = await resolve_company(session, redis, body.name, body.website)
    scan, reused = await get_or_create_scan(session, redis, company, force=force)
    await session.commit()
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
    return {**ScanResponse.from_scan(scan).model_dump(), "progress": progress}


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
