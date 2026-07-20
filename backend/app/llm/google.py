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

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _gemini_schema(model: type[BaseModel]) -> dict:
    """Gemini's responseSchema is a restricted OpenAPI subset that doesn't
    understand JSON Schema $ref/$defs -- Pydantic's model_json_schema() emits
    those for any nested model (e.g. EnrichmentResult.products), so they must
    be inlined before being sent."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(raw)


class GoogleAIStudioProvider:
    """Gemini + Gemma via Google AI Studio's REST API (§10)."""

    name = "google_ai_studio"

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
            return await self._call(key, prompt, system=system, schema=schema, temperature=temperature, timeout=timeout)

        return await routed_complete(self.redis, self.pool, raw_call)

    async def _call(
        self,
        key: Key,
        prompt: str,
        *,
        system: str | None,
        schema: type[BaseModel] | None,
        temperature: float | None,
        timeout: float,
    ) -> LLMResponse:
        body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        generation_config: dict = {}
        if schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = _gemini_schema(schema)
        if temperature is not None:
            generation_config["temperature"] = temperature
        if generation_config:
            body["generationConfig"] = generation_config

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    GEMINI_URL.format(model=self.model),
                    params={"key": key.secret},
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
        if resp.status_code >= 500:
            raise ProviderCallFailed(f"{self.model} returned {resp.status_code}")
        if resp.status_code >= 400:
            raise ProviderCallFailed(f"{self.model} bad request: {resp.text}")

        data = resp.json()
        candidate = data["candidates"][0]
        text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            tokens_in=usage.get("promptTokenCount"),
            tokens_out=usage.get("candidatesTokenCount"),
            latency_ms=int((time.monotonic() - started) * 1000),
            model=self.model,
        )
