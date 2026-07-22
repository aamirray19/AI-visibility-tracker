import json
import uuid

from app.db.models import ScanEntity
from app.llm.base import LLMResponse
from app.services import evaluation
from app.services.entity_resolution import normalize_entity_name


def _entity(name, *, is_target=False, aliases=None):
    return ScanEntity(
        id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        name=name,
        name_norm=normalize_entity_name(name),
        aliases=aliases or [],
        is_target=is_target,
    )


def test_evaluator_pool_for_google_is_eval_a():
    assert evaluation.evaluator_pool_for("google_ai_studio") == "eval_a"


def test_evaluator_pool_for_groq_is_eval_b():
    assert evaluation.evaluator_pool_for("groq") == "eval_b"


def test_stage_a_detects_target_and_competitor_mentions():
    target = _entity("Acme", is_target=True)
    competitor = _entity("Globex")
    target_mentioned, matched = evaluation.stage_a("I'd recommend Acme or Globex.", [target, competitor])
    assert target_mentioned is True
    assert {e.name for e in matched} == {"Acme", "Globex"}


def test_stage_a_target_not_mentioned():
    target = _entity("Acme", is_target=True)
    target_mentioned, matched = evaluation.stage_a("Try Globex instead.", [target])
    assert target_mentioned is False
    assert matched == []


class FakeEvalProvider:
    model = "llama-3.3-70b-versatile"

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, prompt, *, schema=None, timeout=60.0, **kwargs):
        self.calls += 1
        text = self._responses[min(self.calls - 1, len(self._responses) - 1)]
        return LLMResponse(text=text, latency_ms=10, model=self.model)


GOOD_JSON = json.dumps(
    {
        "sentiment": "positive",
        "recommended": True,
        "rank_position": 1,
        "mentioned_companies": ["Acme", "Globex"],
        "confidence": 0.9,
        "reasoning": "Acme is listed first and praised.",
    }
)


async def test_stage_b_parses_valid_json_on_first_try():
    provider = FakeEvalProvider([GOOD_JSON])
    result = await evaluation.stage_b(
        provider, prompt_text="best tools?", response_text="Acme is great, then Globex.",
        target_name="Acme", target_mentioned=True,
    )
    assert result.sentiment == "positive"
    assert result.rank_position == 1
    assert provider.calls == 1


async def test_stage_b_repairs_once_on_malformed_json():
    provider = FakeEvalProvider(["not valid json at all", GOOD_JSON])
    result = await evaluation.stage_b(
        provider, prompt_text="best tools?", response_text="Acme is great.",
        target_name="Acme", target_mentioned=True,
    )
    assert result.sentiment == "positive"
    assert provider.calls == 2


async def test_stage_b_gives_up_after_one_failed_repair():
    provider = FakeEvalProvider(["still not json", "also not json"])
    try:
        await evaluation.stage_b(
            provider, prompt_text="best tools?", response_text="Acme is great.",
            target_name="Acme", target_mentioned=True,
        )
        raised = False
    except ValueError:
        raised = True
    assert raised
    assert provider.calls == 2
