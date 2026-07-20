from app.core.lifecycle import transition
from app.db.models import Company, CompanyProfile, Scan
from app.db.repositories.profiles import CompanyProfileRepository
from app.llm.base import LLMProvider, strip_code_fence
from app.llm.render import render_prompt
from app.llm.schemas import VerificationResult
from app.services import entity_resolution

SYSTEM_PROMPT = (
    "You are a fact-checking critic reviewing a company profile before it's "
    "used to monitor AI-generated answers about that company. Be skeptical "
    "and specific."
)

EDITABLE_FIELDS = ("industry", "description", "aliases", "products", "competitors")
CARRIED_FIELDS = ("keywords",)  # never PATCHable, always copied forward from the prior version


async def apply_patch(session, scan: Scan, latest: CompanyProfile, updates: dict) -> CompanyProfile:
    """§7.3 step 1: PATCH /profile. Multiple edits before the first confirm
    update the same v2 row in place; company/website are never accepted
    fields (locked in Phase 1). Either branch clears any stale critic
    feedback, since the profile just changed underneath it."""
    profiles = CompanyProfileRepository(session)

    if latest.source == "user_edited":
        for key in EDITABLE_FIELDS:
            if key in updates:
                setattr(latest, key, updates[key])
        latest.issues = []
        await session.flush()
        return latest

    fields = {key: getattr(latest, key) for key in (*EDITABLE_FIELDS, *CARRIED_FIELDS)}
    fields.update({k: v for k, v in updates.items() if k in EDITABLE_FIELDS})
    return await profiles.create(
        scan_id=scan.id, version=latest.version + 1, source="user_edited", confidence=latest.confidence, **fields
    )


async def critique(provider: LLMProvider, *, company_name: str, profile: CompanyProfile) -> VerificationResult:
    """§7.3 step 3: sends the user's profile back to gemini-2.5-flash as a
    critic. The verifier only advises -- callers must never auto-apply its
    corrections (the user has ground truth no model has)."""
    prompt = render_prompt(
        "verification.jinja",
        company_name=company_name,
        profile={
            "industry": profile.industry,
            "description": profile.description,
            "aliases": profile.aliases,
            "products": profile.products,
            "competitors": profile.competitors,
        },
    )
    llm_response = await provider.complete(prompt, system=SYSTEM_PROMPT, schema=VerificationResult, timeout=60.0)
    return VerificationResult.model_validate_json(strip_code_fence(llm_response.text))


async def accept(session, scan: Scan, company: Company, latest: CompanyProfile) -> CompanyProfile:
    """Writes v3 (`ai_verified`), freezes scan_entities, advances to
    scope_pending. Used whether the critic said 'ok' or the user confirmed a
    second time despite flagged issues (§7.3 step 4) -- both mean "this
    profile is final"."""
    profiles = CompanyProfileRepository(session)
    v3 = await profiles.create(
        scan_id=scan.id,
        version=latest.version + 1,
        source="ai_verified",
        industry=latest.industry,
        description=latest.description,
        aliases=latest.aliases,
        keywords=latest.keywords,
        products=latest.products,
        competitors=latest.competitors,
        confidence=latest.confidence,
        warnings=latest.warnings,
    )
    await entity_resolution.freeze_entities(session, scan, company, v3)
    transition(scan, "scope_pending")
    return v3
