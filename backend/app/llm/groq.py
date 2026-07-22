import time

import httpx
from pydantic import BaseModel

from app.core.keypool import Key, KeyPool
from app.core.ratelimit import record_limits_from_headers
from app.llm.base import (
    LLMResponse,
    PermanentKeyFailure,
    ProviderCallFailed,
    RateLimited,
    routed_complete,
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider:
    """GPT-OSS + Llama via Groq's OpenAI-compatible API (§10).

    Web search is Groq's server-executed tool: the model runs the search and
    returns the final assistant text plus the cited URLs in one round trip,
    so there's no client-side tool loop to drive. Exact response field names
    for citations are the §10 "verify model IDs" open item -- confirm against
    a live call before Phase 21, tighten `_extract_citations` if needed.
    """

    name = "groq"

    def __init__(self, redis, pool: KeyPool, model: str):
        self.redis = redis
        self.pool = pool
        self.model = model

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema: type[BaseModel] | None = None,
        tools: list[str] | None = None,
        temperature: float | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        async def raw_call(key: Key) -> LLMResponse:
            return await self._call(
                key, prompt, system=system, schema=schema, tools=tools, temperature=temperature, timeout=timeout
            )

        return await routed_complete(self.redis, self.pool, raw_call)

    async def _call(
        self,
        key: Key,
        prompt: str,
        *,
        system: str | None,
        schema: type[BaseModel] | None,
        tools: list[str] | None,
        temperature: float | None,
        timeout: float,
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict = {"model": self.model, "messages": messages}
        if schema is not None:
            body["response_format"] = {"type": "json_object"}
        if tools and "web_search" in tools:
            body["tools"] = [{"type": "browser_search"}]
        if temperature is not None:
            body["temperature"] = temperature

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {key.secret}"},
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise ProviderCallFailed(f"{self.model} timed out") from exc
        except httpx.RequestError as exc:
            raise ProviderCallFailed(str(exc)) from exc

        await record_limits_from_headers(self.redis, key.id, resp.headers)

        if resp.status_code == 429:
            raise RateLimited(int(resp.headers.get("retry-after", 30)))
        if resp.status_code in (401, 403):
            raise PermanentKeyFailure(key.id)
        if resp.status_code == 400 and "blocked_api_access" in resp.text:
            raise PermanentKeyFailure(key.id)  # spend limit hit -- org-level, key is 1:1 with org (§10.1)
        if resp.status_code >= 500:
            raise ProviderCallFailed(f"{self.model} returned {resp.status_code}")
        if resp.status_code >= 400:
            raise ProviderCallFailed(f"{self.model} bad request: {resp.text}")

        data = resp.json()
        message = data["choices"][0]["message"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=message.get("content") or "",
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
            latency_ms=int((time.monotonic() - started) * 1000),
            model=self.model,
            citations=self._extract_citations(message),
        )

    @staticmethod
    def _extract_citations(message: dict) -> list[dict]:
        executed = message.get("executed_tools") or []
        citations = []
        for tool_call in executed:
            for result in tool_call.get("search_results", {}).get("results", []):
                if url := result.get("url"):
                    citations.append({"url": url, "domain": httpx.URL(url).host})
        return citations
