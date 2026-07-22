import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.metrics import ScanMetricsRepository
from app.db.repositories.scans import ScanRepository
from app.deps import get_db, require_api_key

router = APIRouter(prefix="/scans", tags=["dashboard"], dependencies=[Depends(require_api_key)])


@router.get("/{scan_id}/dashboard")
async def get_dashboard(scan_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> dict:
    """§7.11/§12: one read of scan_metrics, no read-time aggregation. `status`
    is included alongside the metrics so the frontend can render the
    completed_with_gaps banner and provider-set stamp (§13.2) without a
    second call."""
    scans = ScanRepository(session)
    scan = await scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")

    metrics_repo = ScanMetricsRepository(session)
    row = await metrics_repo.get(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="dashboard not available yet")

    return {"status": scan.status, "status_detail": scan.status_detail, **row.metrics}
