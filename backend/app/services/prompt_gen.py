import hashlib
import re

from rapidfuzz import fuzz

from app.llm.base import LLMProvider, strip_code_fence
from app.llm.render import render_prompt
from app.llm.schemas import PromptGenerationResult

BATCH_SIZE = 15
NEAR_DUPE_THRESHOLD = 90
MIN_WORDS = 5
ASK_BUFFER_RATIO = 1.2  # over-ask per category to survive dedup/quality filtering

CATEGORY_MIX = {
    "informational": 0.30,
    "commercial": 0.30,
    "competitor_discovery": 0.25,
    "product_specific": 0.15,
}

# §7.6: brand-only mode has no competitors to discover -- that 25% folds
# into commercial (category-probing) questions instead.
BRAND_ONLY_CATEGORY_MIX = {
    "informational": 0.30,
    "commercial": 0.55,
    "product_specific": 0.15,
}

CATEGORY_TARGET = {
    "informational": "category",
    "commercial": "category",
    "competitor_discovery": "competitor",
    "product_specific": "brand",
}

CATEGORY_DESCRIPTIONS = {
    "informational": "general information-seeking questions about the problem space, with no vendor named",
    "commercial": '"best tools for X" / buying-guide style questions, with no vendor named',
    "competitor_discovery": "questions asking for alternatives to a named competitor",
    "product_specific": "questions asking specifically about this company/product by name",
}


def _category_targets(total: int, mix: dict[str, float]) -> dict[str, int]:
    """Largest-remainder rounding so the per-category counts sum exactly to `total`."""
    exact = {cat: total * share for cat, share in mix.items()}
    floors = {cat: int(v) for cat, v in exact.items()}
    remainder = total - sum(floors.values())
    by_fraction = sorted(exact, key=lambda c: exact[c] - floors[c], reverse=True)
    for cat in by_fraction[:remainder]:
        floors[cat] += 1
    return floors


def _dedupe_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()


def _passes_quality(text: str) -> bool:
    if len(text.split()) < MIN_WORDS:
        return False
    lowered = text.lower()
    return "as an ai" not in lowered and "[company]" not in lowered


def _is_near_duplicate(text: str, accepted_texts: list[str]) -> bool:
    return any(fuzz.token_set_ratio(text, existing) > NEAR_DUPE_THRESHOLD for existing in accepted_texts)


async def _ask_category(
    provider: LLMProvider,
    *,
    company_name: str,
    industry: str | None,
    competitors: list[str],
    scope_text: str,
    category: str,
    count: int,
) -> list[str]:
    """One or more LLM calls, batched to <=BATCH_SIZE per call -- one long
    structured call degrades and starts repeating itself (§7.5)."""
    texts: list[str] = []
    remaining = count
    while remaining > 0:
        batch_n = min(BATCH_SIZE, remaining)
        prompt = render_prompt(
            "prompt_generation.jinja",
            company_name=company_name,
            industry=industry,
            competitors=competitors,
            scope_text=scope_text,
            category=category,
            category_description=CATEGORY_DESCRIPTIONS[category],
            count=batch_n,
        )
        llm_response = await provider.complete(
            prompt, schema=PromptGenerationResult, temperature=0.9, timeout=60.0
        )
        result = PromptGenerationResult.model_validate_json(strip_code_fence(llm_response.text))
        texts.extend(p.text for p in result.prompts)
        remaining -= batch_n
    return texts


def _filter_candidates(
    texts: list[str], category: str, seen_hashes: set[str], accepted_texts: list[str], limit: int
) -> list[dict]:
    accepted = []
    for raw in texts:
        if len(accepted) >= limit:
            break
        text = raw.strip()
        if not _passes_quality(text):
            continue
        dedupe_hash = _dedupe_hash(text)
        if dedupe_hash in seen_hashes:
            continue
        if _is_near_duplicate(text, accepted_texts):
            continue
        seen_hashes.add(dedupe_hash)
        accepted_texts.append(text)
        accepted.append(
            {"text": text, "category": category, "target": CATEGORY_TARGET[category], "dedupe_hash": dedupe_hash}
        )
    return accepted


async def generate(
    provider: LLMProvider,
    *,
    company_name: str,
    industry: str | None,
    competitors: list[str],
    scope_categories: list[str],
    brand_only: bool,
    target_count: int = 50,
) -> tuple[list[dict], list[str]]:
    """§7.5/§7.6: batched generation + validation pipeline. Returns
    (accepted prompt dicts, warnings) -- ready for `prompts.create(**p)`."""
    ask_count = max(target_count + 3, round(target_count * ASK_BUFFER_RATIO))
    mix = BRAND_ONLY_CATEGORY_MIX if brand_only else CATEGORY_MIX
    targets = _category_targets(target_count, mix)
    ask_targets = _category_targets(ask_count, mix)
    scope_text = ", ".join(c.replace("_", " ") for c in scope_categories)

    seen_hashes: set[str] = set()
    accepted_texts: list[str] = []
    accepted_by_category: dict[str, list[dict]] = {cat: [] for cat in mix}

    for category, target_n in targets.items():
        candidates = await _ask_category(
            provider,
            company_name=company_name,
            industry=industry,
            competitors=competitors,
            scope_text=scope_text,
            category=category,
            count=ask_targets[category],
        )
        accepted_by_category[category] = _filter_candidates(
            candidates, category, seen_hashes, accepted_texts, limit=target_n
        )

    total = sum(len(v) for v in accepted_by_category.values())
    if total < target_count:
        # one regeneration round for whichever categories fell short
        for category, target_n in targets.items():
            shortfall = target_n - len(accepted_by_category[category])
            if shortfall <= 0:
                continue
            extra = await _ask_category(
                provider,
                company_name=company_name,
                industry=industry,
                competitors=competitors,
                scope_text=scope_text,
                category=category,
                count=shortfall * 2,  # buffer to absorb filtering losses
            )
            accepted_by_category[category].extend(
                _filter_candidates(extra, category, seen_hashes, accepted_texts, limit=shortfall)
            )

    accepted = [p for cat_prompts in accepted_by_category.values() for p in cat_prompts]
    warnings = ["prompt_shortfall"] if len(accepted) < target_count else []
    return accepted, warnings
