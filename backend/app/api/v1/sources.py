import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_api_key

router = APIRouter(prefix="/scans", tags=["sources"], dependencies=[Depends(require_api_key)])

SOURCES_SQL = text(
    """
    select c->>'domain' as source, count(distinct r.id) as responses
    from ai_responses r, jsonb_array_elements(r.citations) c
    where r.scan_id = :scan_id and r.status = 'success'
    group by 1 order by 2 desc limit 20
    """
)


@router.get("/{scan_id}/sources")
async def get_sources(scan_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> dict:
    """§7.8: "Where AI gets its information" -- top cited domains for this scan."""
    result = await session.execute(SOURCES_SQL, {"scan_id": str(scan_id)})
    return {"sources": [{"source": row.source, "responses": row.responses} for row in result]}
