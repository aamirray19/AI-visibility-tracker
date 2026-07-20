from app.core.keypool import PoolExhausted
from app.llm.base import LLMProvider

EXEC_TIMEOUT_S = 60.0


async def execute(provider: LLMProvider, provider_name: str, prompt_text: str) -> dict:
    """§7.7: calls the execution provider, returns ai_responses-shaped
    fields. `model` is always populated (the column is NOT NULL) even on
    failure/skip, since we know which model we were calling regardless of
    outcome.

    §13.3's execution-side asymmetry: a pool breaker (PoolExhausted) is not
    a job failure -- it's a skip, so the scan can still complete with the
    other provider. Any other exception (exhausted retries, a genuine 4xx)
    is a real failure."""
    tools = ["web_search"] if provider_name == "groq" else None
    try:
        response = await provider.complete(prompt_text, tools=tools, timeout=EXEC_TIMEOUT_S)
    except PoolExhausted:
        return {"status": "skipped", "model": provider.model}
    except Exception as exc:
        return {"status": "failed", "model": provider.model, "error_code": type(exc).__name__}

    return {
        "status": "success",
        "model": response.model,
        "raw_response": response.text,
        "citations": response.citations,
        "latency_ms": response.latency_ms,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "cost_usd": response.cost_usd,
        "api_key_id": response.key_id,
    }
