import re
import unicodedata

from rapidfuzz import fuzz

from app.db.models import Company, CompanyProfile, Scan, ScanEntity
from app.db.repositories.entities import ScanEntityRepository

ENTITY_SUFFIXES = {"inc", "ltd", "llc", "corp", "gmbh", "pvt", "pte", "co"}
FUZZY_MATCH_THRESHOLD = 88
SHORT_NAME_MAX_CHARS = 3  # §11 trap: "Box"/"Arc"/"Hex" get exact-only matching


def normalize_entity_name(name: str) -> str:
    """§11: lowercase, NFKD-fold, strip legal suffixes, strip punctuation,
    collapse whitespace."""
    folded = unicodedata.normalize("NFKD", name.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s]", " ", folded)
    tokens = [t for t in cleaned.split() if t not in ENTITY_SUFFIXES]
    return " ".join(tokens)


def _normalize_text_for_matching(text: str) -> str:
    """Same normalization family as entity names, applied to free text so
    word-boundary checks compare like-for-like."""
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", " ", folded)


def _word_boundary_present(needle_norm: str, haystack_norm: str) -> bool:
    """§11 trap: substring false positives ("Notion" inside "notionally").
    Always match on word boundaries, never a plain `in` check."""
    if not needle_norm:
        return False
    return re.search(r"\b" + re.escape(needle_norm) + r"\b", haystack_norm) is not None


def mentioned_entities_in_text(text: str, entities: list[ScanEntity]) -> list[ScanEntity]:
    """Stage A (§7.9): deterministic, no LLM. An entity counts as mentioned
    if its name or any alias appears as a word-boundary match in the text.
    This alone produces `target_mentioned` and the known-competitor set."""
    haystack = _normalize_text_for_matching(text)
    matched = []
    for entity in entities:
        candidates = [entity.name_norm, *(normalize_entity_name(a) for a in entity.aliases)]
        if any(_word_boundary_present(c, haystack) for c in candidates if c):
            matched.append(entity)
    return matched


def resolve_mention(
    raw_name: str, *, entities: list[ScanEntity], text: str, citations: list[dict]
) -> ScanEntity | None:
    """§11 match order, first hit wins -- resolves one of Stage B's free-text
    `mentioned_companies` entries against the frozen entity set:
    1. Exact on name_norm
    2. Exact on any alias (normalized)
    3. Entity's domain root corresponds to this name AND appears in the
       response text or citations (corroborating evidence, not "any domain
       anywhere matches any name" -- §11 doesn't spell out the exact
       correspondence rule, so this ties the domain check to the name it's
       meant to confirm)
    4. Fuzzy: rapidfuzz.token_set_ratio >= 88 (short names excluded)
    5. No match -> None (discovered company, entity_id stays null)
    """
    name_norm = normalize_entity_name(raw_name)
    if not name_norm:
        return None

    for entity in entities:
        if entity.name_norm == name_norm:
            return entity
        if any(normalize_entity_name(a) == name_norm for a in entity.aliases):
            return entity

    text_lower = text.lower()
    citation_domains = {c.get("domain", "").lower() for c in citations if c.get("domain")}
    for entity in entities:
        if not entity.domain:
            continue
        domain = entity.domain.lower()
        domain_root = domain.split(".")[0]
        domain_matches_name = domain_root == name_norm or domain_root in name_norm or name_norm in domain_root
        domain_present = domain in citation_domains or domain in text_lower
        if domain_matches_name and domain_present:
            return entity

    if len(name_norm) > SHORT_NAME_MAX_CHARS:
        best_entity, best_ratio = None, 0
        for entity in entities:
            ratio = fuzz.token_set_ratio(name_norm, entity.name_norm)
            if ratio > best_ratio:
                best_entity, best_ratio = entity, ratio
        if best_entity is not None and best_ratio >= FUZZY_MATCH_THRESHOLD:
            return best_entity

    return None


def collapse_discovered_names(raw_names: list[str]) -> dict[str, str]:
    """§11: discovered names need their own dedupe -- "Hub Spot", "HubSpot",
    "hubspot.com" from different responses collapse into one. Returns a
    mapping from each raw name to a canonical representative. Run at
    aggregation time (Phase 10) over the full `entity_id IS NULL` set, not
    per-response."""
    canonical_by_norm: dict[str, str] = {}
    result: dict[str, str] = {}
    for raw in raw_names:
        norm = normalize_entity_name(raw)
        matched_key = next(
            (existing for existing in canonical_by_norm if fuzz.token_set_ratio(norm, existing) >= FUZZY_MATCH_THRESHOLD),
            None,
        )
        if matched_key is None:
            canonical_by_norm[norm] = raw
            matched_key = norm
        result[raw] = canonical_by_norm[matched_key]
    return result


async def freeze_entities(session, scan: Scan, company: Company, profile: CompanyProfile) -> None:
    """§7.3: flattens target + aliases + product names + competitors into
    scan_entities. Called once, on final profile acceptance -- this table is
    frozen from here on; every downstream metric depends on it (§11)."""
    entities = ScanEntityRepository(session)

    product_names = [p.get("name") for p in profile.products if p.get("name")]
    target_aliases = [*profile.aliases, *product_names]
    await entities.create(
        scan_id=scan.id,
        name=company.name,
        name_norm=normalize_entity_name(company.name),
        domain=company.domain,
        aliases=target_aliases,
        is_target=True,
    )

    for competitor in profile.competitors:
        name = competitor.get("name")
        if not name:
            continue
        await entities.create(
            scan_id=scan.id,
            name=name,
            name_norm=normalize_entity_name(name),
            domain=competitor.get("domain"),
            aliases=competitor.get("aliases") or [],
            is_target=False,
        )
