from app.db.models import ScanEntity
from app.llm.base import LLMProvider, strip_code_fence
from app.llm.render import render_prompt
from app.llm.schemas import EvaluationResult
from app.services.entity_resolution import mentioned_entities_in_text

EVAL_A_EXECUTION_PROVIDER = "google_ai_studio"


def evaluator_pool_for(execution_provider: str) -> str:
    """§7.9 routing rule: eval_a judges Gemma responses, eval_b judges
    GPT-OSS -- same model/prompt/schema either way, purely to split load and
    isolate failure domains."""
    return "eval_a" if execution_provider == EVAL_A_EXECUTION_PROVIDER else "eval_b"


def stage_a(raw_response: str, entities: list[ScanEntity]) -> tuple[bool, list[ScanEntity]]:
    """Deterministic, no LLM (§7.9). Returns (target_mentioned, mentioned_entities)."""
    mentioned = mentioned_entities_in_text(raw_response, entities)
    target_mentioned = any(e.is_target for e in mentioned)
    return target_mentioned, mentioned


async def stage_b(
    provider: LLMProvider,
    *,
    prompt_text: str,
    response_text: str,
    target_name: str,
    target_mentioned: bool,
) -> EvaluationResult:
    """LLM evaluator (§7.9). Llama 3.3 70B has no native strict JSON-schema
    output the way Gemini does -- use JSON mode, validate with Pydantic, and
    allow one repair re-prompt on a parse failure before giving up."""
    prompt = render_prompt(
        "evaluation.jinja",
        prompt_text=prompt_text,
        response_text=response_text,
        target_name=target_name,
        target_mentioned=target_mentioned,
    )
    llm_response = await provider.complete(prompt, schema=EvaluationResult, timeout=60.0)
    try:
        return EvaluationResult.model_validate_json(strip_code_fence(llm_response.text))
    except ValueError:
        repair_prompt = (
            f"{prompt}\n\nYour previous response could not be parsed as valid JSON matching the "
            "required schema. Return ONLY valid JSON this time, with no other text."
        )
        repaired = await provider.complete(repair_prompt, schema=EvaluationResult, timeout=60.0)
        return EvaluationResult.model_validate_json(strip_code_fence(repaired.text))
