"""§20.2 golden-set runner. Manual only -- costs real tokens against a real
provider and the model is non-deterministic, so this is never a CI gate.

Run whenever the evaluation.jinja template, MODEL_EVALUATION, or the eval
provider changes:

    cd backend && python -m tests.golden.run_golden

Requires real GROQ_EVAL_A_KEYS/GROQ_EVAL_B_KEYS in the environment (see
backend/.env) -- there are none in local dev by design (Phase 21 is the only
phase that spends real LLM tokens, per plan.md's Global Constraints).
"""

import asyncio

import redis.asyncio as redis_asyncio

from app.config import settings
from app.core.keypool import build_pools
from app.llm.groq import GroqProvider
from app.services import evaluation
from tests.golden.cases import CASES


async def main() -> None:
    redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
    pools = build_pools(settings)
    provider = GroqProvider(redis_client, pools["groq_eval_a"], settings.model_evaluation)

    passed, failed = 0, 0
    for case in CASES:
        result = await evaluation.stage_b(
            provider,
            prompt_text=case["prompt_text"],
            response_text=case["response_text"],
            target_name=case["target_name"],
            target_mentioned=case["expected"]["target_mentioned"],
        )
        actual = {
            "sentiment": result.sentiment,
            "target_mentioned": case["expected"]["target_mentioned"],  # Stage A is authoritative, not re-checked here
            "recommended": result.recommended,
            "rank_position": result.rank_position,
        }
        mismatches = {k: (v, actual[k]) for k, v in case["expected"].items() if actual[k] != v}

        include = case.get("expected_mentioned_companies_include", [])
        missing = [name for name in include if name not in result.mentioned_companies]

        if not mismatches and not missing:
            passed += 1
            print(f"PASS  {case['name']}")
        else:
            failed += 1
            print(f"FAIL  {case['name']}")
            for field, (expected, got) in mismatches.items():
                print(f"        {field}: expected {expected!r}, got {got!r}")
            if missing:
                print(f"        expected mentioned_companies to include {missing}, got {result.mentioned_companies}")

    print(f"\n{passed} passed, {failed} failed out of {len(CASES)}")
    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
