import json
import random

from app.llm.base import LLMResponse
from app.services import prompt_gen

_WORD_POOL = [f"topic{i}" for i in range(300)]


class FakePromptProvider:
    """Each call returns 15 structurally unrelated candidate prompts (random
    word sequences with no shared frame) -- empirically verified to stay
    below the near-dupe threshold across the whole run, so `generate()` can
    actually reach its 50-prompt target against this fake."""

    model = "gemini-2.5-flash"

    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)
        self.calls = 0

    async def complete(self, prompt, *, system=None, schema=None, tools=None, temperature=None, timeout=60.0):
        self.calls += 1
        texts = [" ".join(self._rng.sample(_WORD_POOL, 8)) for _ in range(15)]
        return LLMResponse(
            text=json.dumps({"prompts": [{"text": t} for t in texts]}), latency_ms=10, model=self.model
        )


class RepeatingProvider:
    """Always returns the same handful of prompts -- every call after the
    first is entirely deduped away, forcing a shortfall."""

    model = "gemini-2.5-flash"

    async def complete(self, prompt, *, system=None, schema=None, tools=None, temperature=None, timeout=60.0):
        texts = [f"this is always the exact same repeated prompt text number {i}" for i in range(3)]
        return LLMResponse(
            text=json.dumps({"prompts": [{"text": t} for t in texts]}), latency_ms=10, model=self.model
        )


# --- pure filter unit tests -------------------------------------------------


def test_category_targets_sum_to_total():
    targets = prompt_gen._category_targets(50, prompt_gen.CATEGORY_MIX)
    assert sum(targets.values()) == 50


def test_category_targets_hold_normal_mix_proportions():
    targets = prompt_gen._category_targets(50, prompt_gen.CATEGORY_MIX)
    assert targets["informational"] == 15
    assert targets["commercial"] == 15
    assert targets["competitor_discovery"] + targets["product_specific"] == 20


def test_category_targets_brand_only_reallocates_competitor_discovery():
    targets = prompt_gen._category_targets(50, prompt_gen.BRAND_ONLY_CATEGORY_MIX)
    assert "competitor_discovery" not in targets
    assert targets["commercial"] == 28  # 55% of 50, largest-remainder rounded
    assert sum(targets.values()) == 50


def test_passes_quality_rejects_short_prompt():
    assert prompt_gen._passes_quality("too short") is False


def test_passes_quality_rejects_as_an_ai_phrase():
    assert prompt_gen._passes_quality("As an AI, what would you recommend for this situation") is False


def test_passes_quality_rejects_company_placeholder():
    assert prompt_gen._passes_quality("Is [company] a good choice for this kind of problem") is False


def test_passes_quality_accepts_a_realistic_prompt():
    assert prompt_gen._passes_quality("What are the best tools for managing a small team's workflow") is True


def test_dedupe_hash_is_stable_across_whitespace_and_case():
    a = prompt_gen._dedupe_hash("What Is The Best Tool")
    b = prompt_gen._dedupe_hash("  what is   the best tool  ")
    assert a == b


def test_is_near_duplicate_true_for_reworded_text():
    accepted = ["What are the best tools for small teams in 2026"]
    assert prompt_gen._is_near_duplicate("What are the best tools for small teams in 2026?", accepted) is True


def test_is_near_duplicate_false_for_unrelated_text():
    accepted = ["What are the best tools for small teams in 2026"]
    assert prompt_gen._is_near_duplicate("How does pricing usually work for enterprise contracts", accepted) is False


def test_filter_candidates_rejects_exact_and_near_duplicates_and_bad_quality():
    texts = [
        "What are the best tools for small teams in 2026",
        "What are the best tools for small teams in 2026",  # exact dupe
        "What are the best tools for small teams in 2026?",  # near dupe
        "too short",  # quality
        "How does pricing usually work for enterprise contracts today",  # genuinely distinct, accepted
    ]
    seen_hashes: set[str] = set()
    accepted_texts: list[str] = []
    result = prompt_gen._filter_candidates(texts, "informational", seen_hashes, accepted_texts, limit=10)
    assert len(result) == 2
    assert result[0]["category"] == "informational"
    assert result[0]["target"] == "category"


# --- generate() integration tests ------------------------------------------


async def test_generate_normal_mode_hits_category_mix():
    accepted, warnings = await prompt_gen.generate(
        FakePromptProvider(),
        company_name="Acme",
        industry="SaaS",
        competitors=["Globex", "Initech"],
        scope_categories=["pricing_discussions"],
        brand_only=False,
    )
    assert warnings == []
    assert len(accepted) == 50
    counts = {cat: sum(1 for p in accepted if p["category"] == cat) for cat in prompt_gen.CATEGORY_MIX}
    assert counts == prompt_gen._category_targets(50, prompt_gen.CATEGORY_MIX)


async def test_generate_respects_a_smaller_target_count():
    """settings.prompt_count must actually control how many prompts get
    generated -- this was a real bug: target_count had no parameter at all
    and generate() always produced exactly 50 regardless of config, which
    meant PROMPT_COUNT was silently dead configuration (caught only by a
    real pipeline run spending 100 real executions instead of the intended
    12)."""
    accepted, warnings = await prompt_gen.generate(
        FakePromptProvider(),
        company_name="Acme",
        industry="SaaS",
        competitors=["Globex"],
        scope_categories=[],
        brand_only=False,
        target_count=20,
    )
    assert warnings == []
    assert len(accepted) == 20


async def test_generate_brand_only_mode_has_no_competitor_discovery():
    accepted, warnings = await prompt_gen.generate(
        FakePromptProvider(),
        company_name="Acme",
        industry="SaaS",
        competitors=[],
        scope_categories=[],
        brand_only=True,
    )
    assert warnings == []
    assert len(accepted) == 50
    assert not any(p["category"] == "competitor_discovery" for p in accepted)
    counts = {cat: sum(1 for p in accepted if p["category"] == cat) for cat in prompt_gen.BRAND_ONLY_CATEGORY_MIX}
    assert counts == prompt_gen._category_targets(50, prompt_gen.BRAND_ONLY_CATEGORY_MIX)


async def test_generate_shortfall_proceeds_with_warning():
    accepted, warnings = await prompt_gen.generate(
        RepeatingProvider(),
        company_name="Acme",
        industry="SaaS",
        competitors=["Globex"],
        scope_categories=[],
        brand_only=False,
    )
    assert warnings == ["prompt_shortfall"]
    assert len(accepted) < 50
    # dedupe actually held: no duplicate dedupe_hash values across categories
    assert len({p["dedupe_hash"] for p in accepted}) == len(accepted)
