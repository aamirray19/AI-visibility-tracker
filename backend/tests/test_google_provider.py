import json

import httpx
import pytest

import app.llm.google as google_mod
from app.core.keypool import Key, KeyPool
from app.llm.base import PermanentKeyFailure, ProviderCallFailed, RateLimited
from app.llm.google import _gemini_schema
from app.llm.schemas import EnrichmentResult

KEY = Key(id="k1", secret="sekret", org="org1")


def _find_key(node, target: str) -> bool:
    if isinstance(node, dict):
        return target in node or any(_find_key(v, target) for v in node.values())
    if isinstance(node, list):
        return any(_find_key(item, target) for item in node)
    return False


def test_gemini_schema_inlines_nested_models_and_drops_refs():
    # EnrichmentResult nests EnrichmentProduct/EnrichmentCompetitor lists --
    # Pydantic's model_json_schema() emits $defs/$ref for those, which
    # Gemini's responseSchema rejects outright (a real 400 caught in Phase 21).
    raw = EnrichmentResult.model_json_schema()
    assert "$defs" in raw and _find_key(raw, "$ref")

    resolved = _gemini_schema(EnrichmentResult)
    assert not _find_key(resolved, "$defs")
    assert not _find_key(resolved, "$ref")
    assert resolved["properties"]["products"]["items"]["properties"]["name"]["type"] == "string"
    assert resolved["properties"]["competitors"]["items"]["properties"]["name"]["type"] == "string"


def _patch_transport(monkeypatch, handler):
    orig_client = httpx.AsyncClient

    def _patched(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(google_mod.httpx, "AsyncClient", _patched)


async def test_complete_parses_text_and_usage(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "hello world"}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
            },
        )

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    response = await provider.complete("hi")
    assert response.text == "hello world"
    assert response.tokens_in == 10
    assert response.tokens_out == 5
    assert response.model == "gemini-2.5-flash"


async def test_complete_sends_temperature_when_given(redis_client, monkeypatch):
    seen_bodies = []

    async def handler(request):
        seen_bodies.append(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    await provider.complete("hi", temperature=0.9)
    body = json.loads(seen_bodies[0])
    assert body["generationConfig"]["temperature"] == 0.9


async def test_complete_omits_temperature_when_not_given(redis_client, monkeypatch):
    seen_bodies = []

    async def handler(request):
        seen_bodies.append(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    await provider.complete("hi")
    body = json.loads(seen_bodies[0])
    assert "generationConfig" not in body


async def test_complete_sends_dereferenced_schema_on_the_wire(redis_client, monkeypatch):
    seen_bodies = []

    async def handler(request):
        seen_bodies.append(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    await provider.complete("hi", schema=EnrichmentResult)
    body = json.loads(seen_bodies[0])
    assert not _find_key(body["generationConfig"]["responseSchema"], "$ref")
    assert not _find_key(body["generationConfig"]["responseSchema"], "$defs")


async def test_429_raises_rate_limited_with_retry_after(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(429, headers={"retry-after": "12"})

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    with pytest.raises(Exception) as exc_info:
        await provider._call(KEY, "hi", system=None, schema=None, temperature=None, timeout=5.0)
    assert isinstance(exc_info.value, RateLimited)
    assert exc_info.value.retry_after_s == 12


async def test_403_raises_permanent_key_failure(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(403)

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    with pytest.raises(PermanentKeyFailure):
        await provider._call(KEY, "hi", system=None, schema=None, temperature=None, timeout=5.0)


async def test_500_raises_provider_call_failed(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(500)

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    with pytest.raises(ProviderCallFailed):
        await provider._call(KEY, "hi", system=None, schema=None, temperature=None, timeout=5.0)
