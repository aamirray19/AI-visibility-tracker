import httpx
import pytest

import app.llm.groq as groq_mod
from app.core.keypool import Key, KeyPool
from app.llm.base import PermanentKeyFailure, ProviderCallFailed, RateLimited

KEY = Key(id="k1", secret="sekret", org="org1")


def _patch_transport(monkeypatch, handler):
    orig_client = httpx.AsyncClient

    def _patched(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(groq_mod.httpx, "AsyncClient", _patched)


async def test_complete_parses_text_and_usage(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "final answer"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            },
        )

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = groq_mod.GroqProvider(redis_client, pool, "openai/gpt-oss-120b")

    response = await provider.complete("hi")
    assert response.text == "final answer"
    assert response.tokens_in == 20
    assert response.tokens_out == 8
    assert response.citations == []


async def test_web_search_citations_are_extracted(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "final answer",
                            "executed_tools": [
                                {"search_results": {"results": [{"url": "https://g2.com/acme"}]}}
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            },
        )

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = groq_mod.GroqProvider(redis_client, pool, "openai/gpt-oss-120b")

    response = await provider.complete("hi", tools=["web_search"])
    assert response.citations == [{"url": "https://g2.com/acme", "domain": "g2.com"}]


async def test_429_raises_rate_limited_with_retry_after(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(429, headers={"retry-after": "7"})

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = groq_mod.GroqProvider(redis_client, pool, "openai/gpt-oss-120b")

    with pytest.raises(RateLimited) as exc_info:
        await provider._call(KEY, "hi", system=None, schema=None, tools=None, temperature=None, timeout=5.0)
    assert exc_info.value.retry_after_s == 7


async def test_401_raises_permanent_key_failure(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(401)

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = groq_mod.GroqProvider(redis_client, pool, "openai/gpt-oss-120b")

    with pytest.raises(PermanentKeyFailure):
        await provider._call(KEY, "hi", system=None, schema=None, tools=None, temperature=None, timeout=5.0)


async def test_spend_limit_block_raises_permanent_key_failure(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(400, json={"error": {"code": "blocked_api_access"}})

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = groq_mod.GroqProvider(redis_client, pool, "openai/gpt-oss-120b")

    with pytest.raises(PermanentKeyFailure):
        await provider._call(KEY, "hi", system=None, schema=None, tools=None, temperature=None, timeout=5.0)


async def test_500_raises_provider_call_failed(redis_client, monkeypatch):
    async def handler(request):
        return httpx.Response(500)

    _patch_transport(monkeypatch, handler)
    pool = KeyPool("p", [KEY], "failover", rpm=20, tpm=5000)
    provider = groq_mod.GroqProvider(redis_client, pool, "openai/gpt-oss-120b")

    with pytest.raises(ProviderCallFailed):
        await provider._call(KEY, "hi", system=None, schema=None, tools=None, temperature=None, timeout=5.0)
