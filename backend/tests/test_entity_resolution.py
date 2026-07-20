import uuid

from app.db.models import ScanEntity
from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.scans import ScanRepository
from app.services.entity_resolution import (
    collapse_discovered_names,
    freeze_entities,
    mentioned_entities_in_text,
    normalize_entity_name,
    resolve_mention,
)
from app.services.onboarding import upsert_company


def _entity(name, *, domain=None, aliases=None, is_target=False):
    return ScanEntity(
        id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        name=name,
        name_norm=normalize_entity_name(name),
        domain=domain,
        aliases=aliases or [],
        is_target=is_target,
    )


def test_normalize_entity_name_lowercases_and_strips_suffix():
    assert normalize_entity_name("Acme Widgets Co.") == "acme widgets"


def test_normalize_entity_name_folds_accents():
    assert normalize_entity_name("Café Corp") == "cafe"


def test_normalize_entity_name_strips_punctuation_and_collapses_whitespace():
    assert normalize_entity_name("  Acme, Inc.!! ") == "acme"


def test_normalize_entity_name_short_name_survives_unmodified():
    assert normalize_entity_name("Box") == "box"


async def test_freeze_entities_writes_target_with_aliases_and_product_names(db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id)
    profiles = CompanyProfileRepository(db_session)
    profile = await profiles.create(
        scan_id=scan.id,
        version=3,
        source="ai_verified",
        aliases=["Acme Co"],
        products=[{"name": "Acme Board", "description": "kanban"}],
        competitors=[{"name": "Globex", "domain": "globex.com", "aliases": ["Globex Inc"]}],
    )

    await freeze_entities(db_session, scan, company, profile)

    entities = ScanEntityRepository(db_session)
    rows = await entities.list(scan_id=scan.id)
    target = next(e for e in rows if e.is_target)
    competitor = next(e for e in rows if not e.is_target)

    assert target.name == "Acme"
    assert target.domain == "acme.com"
    assert set(target.aliases) == {"Acme Co", "Acme Board"}

    assert competitor.name == "Globex"
    assert competitor.name_norm == "globex"
    assert competitor.domain == "globex.com"
    assert competitor.aliases == ["Globex Inc"]
    assert len(rows) == 2


# --- Stage A: mentioned_entities_in_text ------------------------------------


def test_mentioned_entities_in_text_finds_name_match():
    acme = _entity("Acme", is_target=True)
    globex = _entity("Globex")
    matched = mentioned_entities_in_text("I'd recommend Acme or Globex for this.", [acme, globex])
    assert {e.name for e in matched} == {"Acme", "Globex"}


def test_mentioned_entities_in_text_finds_alias_match():
    acme = _entity("Acme", is_target=True, aliases=["Acme Analytics"])
    matched = mentioned_entities_in_text("Try using Acme Analytics for this.", [acme])
    assert matched == [acme]


def test_mentioned_entities_in_text_word_boundary_guards_against_substrings():
    """§11 trap: 'Notion' inside 'notionally' must not match."""
    notion = _entity("Notion")
    matched = mentioned_entities_in_text("This notionally helps, but isn't a real recommendation.", [notion])
    assert matched == []


def test_mentioned_entities_in_text_real_word_boundary_still_matches():
    notion = _entity("Notion")
    matched = mentioned_entities_in_text("I'd recommend Notion for this.", [notion])
    assert matched == [notion]


def test_mentioned_entities_in_text_no_match_returns_empty():
    acme = _entity("Acme", is_target=True)
    assert mentioned_entities_in_text("This response mentions nothing relevant.", [acme]) == []


# --- resolve_mention: §11 match order ---------------------------------------


def test_resolve_mention_exact_name_match():
    acme = _entity("Acme", is_target=True)
    globex = _entity("Globex")
    assert resolve_mention("Acme", entities=[acme, globex], text="", citations=[]) == acme


def test_resolve_mention_exact_alias_match():
    acme = _entity("Acme", is_target=True, aliases=["Acme Analytics"])
    assert resolve_mention("Acme Analytics", entities=[acme], text="", citations=[]) == acme


def test_resolve_mention_domain_evidence_when_name_corresponds():
    globex = _entity("Globex Corp", domain="globex.com")
    resolved = resolve_mention(
        "globex", entities=[globex], text="check out globex.com for pricing", citations=[]
    )
    assert resolved == globex


def test_resolve_mention_domain_alone_does_not_resolve_unrelated_name():
    globex = _entity("Globex Corp", domain="globex.com")
    resolved = resolve_mention(
        "acme", entities=[globex], text="check out globex.com for pricing", citations=[]
    )
    assert resolved is None


def test_resolve_mention_fuzzy_match_above_threshold():
    acme = _entity("Acme Corporation")
    resolved = resolve_mention("Acme Corp", entities=[acme], text="", citations=[])
    assert resolved == acme


def test_resolve_mention_short_name_requires_exact_match_no_fuzzy():
    """§11 trap: entities with name_norm <= 3 chars get exact-only matching."""
    box = _entity("Box")
    resolved = resolve_mention("Boxx", entities=[box], text="", citations=[])
    assert resolved is None


def test_resolve_mention_short_name_exact_still_matches():
    box = _entity("Box")
    resolved = resolve_mention("Box", entities=[box], text="", citations=[])
    assert resolved == box


def test_resolve_mention_no_match_returns_none():
    acme = _entity("Acme")
    assert resolve_mention("Totally Unrelated Company", entities=[acme], text="", citations=[]) is None


def test_resolve_mention_empty_name_returns_none():
    acme = _entity("Acme")
    assert resolve_mention("", entities=[acme], text="", citations=[]) is None


# --- collapse_discovered_names -----------------------------------------------


def test_collapse_discovered_names_merges_near_duplicates():
    mapping = collapse_discovered_names(["HubSpot", "Hub Spot", "hubspot"])
    assert len(set(mapping.values())) == 1


def test_collapse_discovered_names_keeps_distinct_names_separate():
    mapping = collapse_discovered_names(["HubSpot", "Salesforce"])
    assert len(set(mapping.values())) == 2
