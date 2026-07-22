import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import INVALID_STATE_TRANSITION
from app.core.errors import AppError
from app.core.lifecycle import transition
from app.db.models import CompanyProfile
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.scans import ScanRepository
from app.deps import get_arq_redis, get_db, require_api_key
from app.services import verification
from app.worker.queues import INTERACTIVE_QUEUE

router = APIRouter(prefix="/scans", tags=["profiles"], dependencies=[Depends(require_api_key)])


class ProductIn(BaseModel):
    name: str
    description: str | None = None


class CompetitorIn(BaseModel):
    name: str
    domain: str | None = None
    aliases: list[str] = []


class PatchProfileRequest(BaseModel):
    """Editable fields only (industry/products/competitors/aliases/description).
    Company and website are resolved and locked in Phase 1 -- not accepted here."""

    industry: str | None = None
    description: str | None = None
    aliases: list[str] | None = None
    products: list[ProductIn] | None = None
    competitors: list[CompetitorIn] | None = None


class ProfileResponse(BaseModel):
    version: int
    source: str
    industry: str | None
    description: str | None
    aliases: list[str]
    keywords: list[str]
    products: list[dict]
    competitors: list[dict]
    confidence: float | None
    warnings: list[str]
    issues: list[dict]

    @classmethod
    def from_model(cls, profile: CompanyProfile) -> "ProfileResponse":
        return cls(
            version=profile.version,
            source=profile.source,
            industry=profile.industry,
            description=profile.description,
            aliases=profile.aliases,
            keywords=profile.keywords,
            products=profile.products,
            competitors=profile.competitors,
            confidence=float(profile.confidence) if profile.confidence is not None else None,
            warnings=profile.warnings,
            issues=profile.issues,
        )


async def _get_scan_or_404(scans: ScanRepository, scan_id: uuid.UUID):
    scan = await scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    return scan


async def _get_profile_or_404(profiles: CompanyProfileRepository, scan_id: uuid.UUID) -> CompanyProfile:
    profile = await profiles.get_latest(scan_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")
    return profile


@router.get("/{scan_id}/profile", response_model=ProfileResponse)
async def get_profile(scan_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> ProfileResponse:
    profiles = CompanyProfileRepository(session)
    profile = await _get_profile_or_404(profiles, scan_id)
    return ProfileResponse.from_model(profile)


@router.patch("/{scan_id}/profile", response_model=ProfileResponse)
async def patch_profile(
    scan_id: uuid.UUID, body: PatchProfileRequest, session: AsyncSession = Depends(get_db)
) -> ProfileResponse:
    scans = ScanRepository(session)
    profiles = CompanyProfileRepository(session)

    scan = await _get_scan_or_404(scans, scan_id)
    if scan.status != "awaiting_verification":
        raise AppError(
            INVALID_STATE_TRANSITION,
            f"Cannot edit profile while scan is '{scan.status}'",
            status_code=409,
            details={"from": scan.status},
        )

    latest = await _get_profile_or_404(profiles, scan_id)
    updates = body.model_dump(exclude_unset=True)

    updated = await verification.apply_patch(session, scan, latest, updates)
    await session.commit()
    return ProfileResponse.from_model(updated)


@router.post("/{scan_id}/profile/confirm", response_model=ProfileResponse, status_code=202)
async def confirm_profile(
    scan_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    arq_redis=Depends(get_arq_redis),
) -> ProfileResponse:
    """§7.3 steps 2-4: first confirm sends the profile to the critic; a
    second confirm (the latest row already carries critic-flagged issues)
    accepts as-is instead of re-critiquing."""
    scans = ScanRepository(session)
    profiles = CompanyProfileRepository(session)
    companies = CompanyRepository(session)

    scan = await _get_scan_or_404(scans, scan_id)
    latest = await _get_profile_or_404(profiles, scan_id)

    transition(scan, "verifying")
    await session.commit()

    if latest.issues:
        company = await companies.get(scan.company_id)
        await verification.accept(session, scan, company, latest)
        await session.commit()
    else:
        await arq_redis.enqueue_job(
            "verify_profile",
            str(scan_id),
            _job_id=f"verify:{scan_id}",
            _queue_name=INTERACTIVE_QUEUE,
        )

    refreshed = await profiles.get_latest(scan_id)
    return ProfileResponse.from_model(refreshed)
