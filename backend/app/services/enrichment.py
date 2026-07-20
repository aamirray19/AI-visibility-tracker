import json

from app.llm.base import LLMProvider, strip_code_fence
from app.llm.render import render_prompt
from app.llm.schemas import EnrichmentResult

CACHE_TTL_S = 7 * 24 * 3600
CACHE_CONFIDENCE_THRESHOLD = 0.7  # nothing below this is cached (§7.2)
LOW_CONFIDENCE_WARNING_THRESHOLD = 0.5

SYSTEM_PROMPT = (
    "You are a company research assistant producing structured company "
    "intelligence for a brand-monitoring tool. Be concise and factual."
)


async def enrich(redis, provider: LLMProvider, *, name: str, domain: str) -> dict:
    """§7.2: gemini-2.5-flash call from name/domain/cached homepage text.
    Never raises on a low-confidence or unknown-company result -- those are
    valid outcomes the human gate (Phase 3) is designed to catch, not
    failures. `cache:enrich:{domain}` is written by onboarding (§7.1) with
    the raw homepage extract; this merges in a `profile` key so a repeat
    scan of the same domain within 7d skips the LLM call entirely."""
    cache_key = f"cache:enrich:{domain}"
    cached_raw = await redis.get(cache_key)
    cached = json.loads(cached_raw) if cached_raw else {}

    if "profile" in cached:
        return cached["profile"]

    homepage_text = cached.get("body_text", "")
    prompt = render_prompt("enrichment.jinja", name=name, domain=domain, homepage_text=homepage_text)
    llm_response = await provider.complete(
        prompt, system=SYSTEM_PROMPT, schema=EnrichmentResult, temperature=0.2, timeout=60.0
    )
    result = EnrichmentResult.model_validate_json(strip_code_fence(llm_response.text))
    profile = _to_profile(result, model=llm_response.model)

    if profile["confidence"] >= CACHE_CONFIDENCE_THRESHOLD:
        cached["profile"] = profile
        await redis.setex(cache_key, CACHE_TTL_S, json.dumps(cached))

    return profile


def _to_profile(result: EnrichmentResult, model: str) -> dict:
    warnings = []
    if result.confidence < LOW_CONFIDENCE_WARNING_THRESHOLD:
        warnings.append("low_confidence")
    if not result.competitors:
        warnings.append("no_competitors")
    return {
        "industry": result.industry,
        "description": result.description,
        "aliases": result.aliases,
        "keywords": result.keywords,
        "products": [p.model_dump() for p in result.products],
        "competitors": [c.model_dump() for c in result.competitors],
        "confidence": result.confidence,
        "warnings": warnings,
        "raw_model_out": result.model_dump(),
        "model": model,
    }
