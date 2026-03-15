#Prompt factory — generates search prompts for a brand visibility campaign.
import json
import logging
from groq import AsyncGroq
from app.core.config import settings

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
You are generating search prompts that real users would type into AI-powered
search tools (ChatGPT, Gemini, Perplexity, etc.) when evaluating or buying.

INPUTS:
- Product Category: {category}
- Brand Name: {brand}

REQUIREMENTS:
1. Generate EXACTLY {target_count} prompts total.
2. EXACTLY {commercial_count} must be "commercial" intent (comparing, pricing, best-of).
3. EXACTLY {info_count} must be "informational" intent (how-it-works, concepts).
4. Prompts must sound like real user searches — natural language only.
5. No duplicates or near-duplicates.
6. Return ONLY a JSON array. No markdown, no explanations.

OUTPUT FORMAT:
[
    {{"text": "Best {category} software for mid-sized companies", "type": "commercial"}},
    {{"text": "How does {category} work?", "type": "informational"}}
]
"""


async def generate_campaign_prompts(brand: str, category: str) -> list[dict]:
    """Generate campaign prompts for a brand/category pair."""
    target_count = settings.PROMPT_TARGET_COUNT
    commercial_count = int(target_count * 0.8)
    info_count = target_count - commercial_count

    prompt = PROMPT_TEMPLATE.format(
        brand=brand,
        category=category,
        target_count=target_count,
        commercial_count=commercial_count,
        info_count=info_count,
    )

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    logger.info("Generating %d prompts for brand=%r category=%r", target_count, brand, category)

    try:
        response = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=4000,
        )

        #extract response
        content = (response.choices[0].message.content or "").strip()
        #convert the response to python object
        data = json.loads(content)

        #edge case1:  to handle different kind of responses
        if isinstance(data, list):
            prompts = data
        else:
            prompts = next((v for v in data.values() if isinstance(v, list)), [])

        #edge case2: to handle bad entries
        prompts = [p for p in prompts if isinstance(p, dict) and p.get("text")]

        #edge case3: to handle extra prompts
        if len(prompts) > target_count:
            prompts = prompts[:target_count]
            logger.debug("Trimmed prompts to %d", target_count)

        if len(prompts) < target_count:
            shortfall = target_count - len(prompts)
            logger.warning("LLM returned %d/%d prompts — padding %d", len(prompts), target_count, shortfall)
            
            current_comm = sum(1 for p in prompts if p.get("type") == "commercial")
            current_info = sum(1 for p in prompts if p.get("type") == "informational")
            
            needed_comm = max(0, commercial_count - current_comm)
            needed_info = max(0, info_count - current_info)
            
            for i in range(needed_comm):
                prompts.append({"text": f"Best {category} platforms for businesses — option {i + 1}", "type": "commercial"})
            
            for i in range(needed_info):
                prompts.append({"text": f"What is {category} and how does it work — guide {i + 1}", "type": "informational"})
            
            while len(prompts) < target_count:
                prompts.append({"text": f"Top rated {category} software — extra {len(prompts)}", "type": "commercial"})

        for p in prompts:
            if p.get("type") not in ("commercial", "informational"):
                p["type"] = "commercial"

        logger.info("Final prompt count: %d", len(prompts))
        return prompts

    except Exception as e:
        logger.error("Prompt generation failed for brand=%r: %s", brand, e, exc_info=True)
        return _fallback_prompts(category, settings.PROMPT_TARGET_COUNT)


def _fallback_prompts(category: str, target_count: int) -> list[dict]:
    """Returns guaranteed 80/20 split generic prompts when LLM is unavailable."""
    commercial_count = int(target_count * 0.8)
    info_count = target_count - commercial_count
    
    prompts = []
    
    for i in range(commercial_count):
        prompts.append({"text": f"Best {category} solutions for businesses — option {i + 1}", "type": "commercial"})
        
    for i in range(info_count):
        prompts.append({"text": f"Complete guide to understanding {category} — part {i + 1}", "type": "informational"})
        
    return prompts
