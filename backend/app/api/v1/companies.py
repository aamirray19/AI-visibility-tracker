from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_redis, require_api_key
from app.services.onboarding import resolve_company

router = APIRouter(prefix="/companies", tags=["companies"], dependencies=[Depends(require_api_key)])


class ResolveCompanyRequest(BaseModel):
    name: str
    website: str


class ResolveCompanyResponse(BaseModel):
    company_id: str
    name: str
    domain: str
    recent_scan_id: str | None = None


@router.post("/resolve", response_model=ResolveCompanyResponse)
async def resolve(
    body: ResolveCompanyRequest,
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> ResolveCompanyResponse:
    company = await resolve_company(session, redis, body.name, body.website)
    await session.commit()
    recent_scan_id = await redis.get(f"scan:recent:{company.domain}")
    return ResolveCompanyResponse(
        company_id=str(company.id),
        name=company.name,
        domain=company.domain,
        recent_scan_id=recent_scan_id,
    )
