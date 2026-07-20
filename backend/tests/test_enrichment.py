import json

from app.llm.base import LLMResponse
from app.services import enrichment

KNOWN_COMPANY = {
    "industry": "SaaS",
    "description": "Project management software",
    "aliases": ["Acme Co"],
    "keywords": ["productivity", "teams"],
    "products": [{"name": "Acme Board", "description": "kanban boards"}],
    "competitors": [{"name": "Globex", "domain": "globex.com", "aliases": []}],
    "is_known": True,
    "confidence": 0.9,
}


class FakeProvider:
    def __init__(self, response_json: dict, model: str = "gemini-2.5-flash"):
        self.response_json = response_json
        self.model = model
        self.calls = 0
        self.last_prompt = None

    async def complete(self, prompt, *, system=None, schema=None, tools=None, temperature=None, timeout=60.0):
        self.calls += 1
        self.last_prompt = prompt
        return LLMResponse(text=json.dumps(self.response_json), latency_ms=10, model=self.model)


async def test_enrich_writes_profile_fields_from_llm_response(redis_client):
    provider = FakeProvider(KNOWN_COMPANY)
    profile = await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert profile["industry"] == "SaaS"
    assert profile["confidence"] == 0.9
    assert profile["warnings"] == []
    assert profile["model"] == "gemini-2.5-flash"
    assert provider.calls == 1


async def test_enrich_sets_low_confidence_warning_below_0_5(redis_client):
    low_confidence = {**KNOWN_COMPANY, "confidence": 0.3, "is_known": False}
    provider = FakeProvider(low_confidence)
    profile = await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert "low_confidence" in profile["warnings"]


async def test_enrich_sets_no_competitors_warning(redis_client):
    no_competitors = {**KNOWN_COMPANY, "competitors": []}
    provider = FakeProvider(no_competitors)
    profile = await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert "no_competitors" in profile["warnings"]


async def test_enrich_never_blocks_on_low_confidence_unknown_company(redis_client):
    unknown = {**KNOWN_COMPANY, "is_known": False, "confidence": 0.1, "competitors": []}
    provider = FakeProvider(unknown)
    profile = await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert profile["industry"] == "SaaS"  # profile still written, not blocked
    assert set(profile["warnings"]) == {"low_confidence", "no_competitors"}


async def test_enrich_uses_cached_homepage_text_as_llm_input(redis_client):
    await redis_client.setex("cache:enrich:acme.com", 3600, json.dumps({"body_text": "we sell widgets"}))
    provider = FakeProvider(KNOWN_COMPANY)
    await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert "we sell widgets" in provider.last_prompt


async def test_enrich_caches_high_confidence_profile_and_skips_llm_on_repeat(redis_client):
    provider = FakeProvider(KNOWN_COMPANY)
    await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert provider.calls == 1

    await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert provider.calls == 1  # second call hit the cache, no new LLM call


async def test_enrich_does_not_cache_low_confidence_profile(redis_client):
    low_confidence = {**KNOWN_COMPANY, "confidence": 0.3}
    provider = FakeProvider(low_confidence)
    await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert provider.calls == 1

    await enrichment.enrich(redis_client, provider, name="Acme", domain="acme.com")
    assert provider.calls == 2  # not cached -- called again
