import json
import logging
from groq import AsyncGroq
from app.core.config import settings

logger = logging.getLogger(__name__)

client = AsyncGroq(api_key=settings.GROQ_API_KEY)


async def generate_brand_list(category: str) -> list[str]:
    category = category.strip()

    prompt = (
        f"List the top 10-15 well-known brands in the '{category}' market. "
        "Return ONLY a JSON array of brand name strings. "
        "No explanations, no markdown, no extra text."
    )

    logger.info("Generating brand list for category=%r", category)

    try:
        response = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": "Return only a JSON array of brand names."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=300
        )

        raw = response.choices[0].message.content or "[]"

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw.replace("json", "").strip()

        data = json.loads(raw)

        # handle multiple response formats
        if isinstance(data, list):
            brands = data
        elif isinstance(data, dict):
            brands = data.get("brands") or []
        else:
            brands = []

        brands = [
            b.strip()
            for b in brands
            if isinstance(b, str) and b.strip()
        ]

        logger.info("Generated %d brands for category=%r", len(brands), category)

        return brands

    except json.JSONDecodeError as e:
        logger.error("Brand list JSON parse failed for category=%r: %s", category, e)
        return []

    except Exception as e:
        logger.error(
            "Brand list generation failed for category=%r: %s",
            category,
            e,
            exc_info=True
        )
        return []