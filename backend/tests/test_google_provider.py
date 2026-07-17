import httpx
import pytest

import app.llm.google as google_mod
from app.core.keypool import Key, KeyPool
from app.llm.base import PermanentKeyFailure, ProviderCallFailed, RateLimited

KEY = Key(id="k1", secret="sekret", org="org1")


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


async def test_429_raises_rate_limited_with_retry_after(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(429, headers={"retry-after": "12"})

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    with pytest.raises(Exception) as exc_info:
        await provider._call(KEY, "hi", system=None, schema=None, timeout=5.0)
    assert isinstance(exc_info.value, RateLimited)
    assert exc_info.value.retry_after_s == 12


async def test_403_raises_permanent_key_failure(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(403)

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    with pytest.raises(PermanentKeyFailure):
        await provider._call(KEY, "hi", system=None, schema=None, timeout=5.0)


async def test_500_raises_provider_call_failed(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(500)

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = google_mod.GoogleAIStudioProvider(redis_client, pool, "gemini-2.5-flash")

    with pytest.raises(ProviderCallFailed):
        await provider._call(KEY, "hi", system=None, schema=None, timeout=5.0)
