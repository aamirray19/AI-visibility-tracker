import json

from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.scans import ScanRepository
from app.llm.base import LLMResponse
from app.services import verification
from app.services.onboarding import upsert_company


class FakeProvider:
    def __init__(self, response_json: dict, model: str = "gemini-2.5-flash"):
        self.response_json = response_json
        self.model = model
        self.calls = 0

    async def complete(self, prompt, *, system=None, schema=None, tools=None, temperature=None, timeout=60.0):
        self.calls += 1
        return LLMResponse(text=json.dumps(self.response_json), latency_ms=10, model=self.model)


async def _make_scan_with_v1(db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status="awaiting_verification")
    profiles = CompanyProfileRepository(db_session)
    v1 = await profiles.create(
        scan_id=scan.id,
        version=1,
        source="ai_generated",
        industry="SaaS",
        aliases=["Acme Co"],
        keywords=["productivity"],
        products=[{"name": "Acme Board"}],
        competitors=[{"name": "Globex", "domain": "globex.com"}],
        confidence=0.8,
    )
    return scan, company, v1


async def test_apply_patch_creates_v2_and_carries_forward_keywords(db_session):
    scan, _, v1 = await _make_scan_with_v1(db_session)
    updated = await verification.apply_patch(db_session, scan, v1, {"industry": "Fintech"})

    assert updated.version == 2
    assert updated.source == "user_edited"
    assert updated.industry == "Fintech"
    assert updated.keywords == ["productivity"]  # carried forward, not editable
    assert updated.aliases == ["Acme Co"]  # untouched field carried forward too


async def test_apply_patch_updates_same_v2_row_in_place_on_repeat_edit(db_session):
    scan, _, v1 = await _make_scan_with_v1(db_session)
    first = await verification.apply_patch(db_session, scan, v1, {"industry": "Fintech"})
    second = await verification.apply_patch(db_session, scan, first, {"description": "we do fintech things"})

    assert second.version == 2  # same row, not a new version
    assert second.industry == "Fintech"
    assert second.description == "we do fintech things"

    profiles = CompanyProfileRepository(db_session)
    all_versions = await profiles.list(scan_id=scan.id)
    assert len(all_versions) == 2  # v1 + the one v2, no v3/v4 from repeat edits


async def test_apply_patch_clears_stale_issues(db_session):
    scan, _, v1 = await _make_scan_with_v1(db_session)
    v2 = await verification.apply_patch(db_session, scan, v1, {"industry": "Fintech"})
    v2.issues = [{"field": "competitors", "value": "Globex", "reason": "not a real competitor"}]
    await db_session.flush()

    v2_again = await verification.apply_patch(db_session, scan, v2, {"description": "new desc"})
    assert v2_again.issues == []


async def test_critique_parses_ok_verdict(db_session):
    scan, _, v1 = await _make_scan_with_v1(db_session)
    provider = FakeProvider({"verdict": "ok", "issues": []})
    result = await verification.critique(provider, company_name="Acme", profile=v1)
    assert result.verdict == "ok"
    assert result.issues == []


async def test_critique_survives_a_markdown_fenced_response(db_session):
    # Reproduces a real failure: Gemma sometimes wraps structured output in
    # a ```json fence even when JSON-only output was requested, which broke
    # this exact call with a pydantic "trailing characters" ValidationError
    # during Phase 21's live run before strip_code_fence() was added.
    class FencedProvider:
        model = "gemma-4-31b-it"

        async def complete(self, prompt, *, system=None, schema=None, tools=None, temperature=None, timeout=60.0):
            return LLMResponse(text='```json\n{"verdict": "ok", "issues": []}\n```', latency_ms=10, model=self.model)

    scan, _, v1 = await _make_scan_with_v1(db_session)
    result = await verification.critique(FencedProvider(), company_name="Acme", profile=v1)
    assert result.verdict == "ok"


async def test_critique_parses_issues_found_verdict(db_session):
    scan, _, v1 = await _make_scan_with_v1(db_session)
    provider = FakeProvider(
        {
            "verdict": "issues_found",
            "issues": [{"field": "competitors", "value": "Globex", "reason": "not a real competitor"}],
        }
    )
    result = await verification.critique(provider, company_name="Acme", profile=v1)
    assert result.verdict == "issues_found"
    assert result.issues[0].field == "competitors"


async def test_accept_writes_v3_freezes_entities_and_advances_to_scope_pending(db_session):
    scan, company, v1 = await _make_scan_with_v1(db_session)
    scan.status = "verifying"  # real callers transition here before calling accept()

    v3 = await verification.accept(db_session, scan, company, v1)

    assert v3.version == 2
    assert v3.source == "ai_verified"
    assert scan.status == "scope_pending"

    entities = ScanEntityRepository(db_session)
    rows = await entities.list(scan_id=scan.id)
    assert len(rows) == 2  # target + the one competitor
