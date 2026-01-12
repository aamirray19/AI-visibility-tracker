import os
import json
from litellm import completion

async def generate_campaign_prompts(brand: str, category: str) -> list[dict]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")
        
    prompt = f"""
    You are generating search prompts that real users would type into AI-powered
    search tools (ChatGPT, Gemini, Perplexity, etc.) when they are evaluating,
    comparing, pricing, or deciding whether to BUY or ADOPT a product or service.

    INPUTS (provided dynamically):
    - Product Category: {category}
    - Brand Name: {brand}

    CRITICAL REQUIREMENTS (DO NOT VIOLATE):

    1. Generate EXACTLY 100 prompts total.

    2. EXACTLY 80 prompts MUST be "commercial" intent.

    Commercial intent means the user is:
    - Comparing brands or vendors
    - Evaluating pricing, plans, or total cost
    - Searching for “best”, “top”, or “alternatives”
    - Asking whether a brand is worth buying or adopting
    - Looking for enterprise, SMB, or industry-specific solutions
    - Comparing {brand} against competitors in {category}

    Examples of VALID commercial intent (generalized):
    - "Best {category} solutions for enterprises"
    - "{brand} vs competitors in {category}"
    - "{brand} pricing and plans"
    - "Is {brand} worth it for large businesses?"
    - "Top alternatives to {brand}"
    - "Best {category} software for small businesses"
    - "Cost comparison of leading {category} platforms"
    - "Which {category} provider is best in 2024?"
    - "{brand} pros and cons compared to competitors"

    Do NOT include:
    - How-it-works explanations
    - Definitions
    - History or background
    - Technical tutorials
    These belong ONLY to informational intent.

    3. EXACTLY 20 prompts MUST be "informational" intent.

    Informational intent means the user is:
    - Learning concepts
    - Understanding how the category works
    - Exploring background or terminology
    - NOT making a buying or adoption decision

    Examples of VALID informational intent (generalized):
    - "How does {category} work?"
    - "What is {category} used for?"
    - "Key features of {category}"
    - "History of {brand}"
    - "How companies use {category}"

    4. Prompts MUST sound like REAL user searches.
    - Natural language only
    - No placeholders like “product X”
    - No marketing slogans
    - No unnatural phrasing

    5. Avoid duplicates or near-duplicates.
    Each prompt must be meaningfully different.

    6. Return ONLY a JSON object.
    - No explanations
    - No headings
    - No markdown
    - No comments

    OUTPUT FORMAT (STRICT):

    [
        {{"text": "Best {category} software for mid-sized companies", "type": "commercial"}},
        {{"text": "{brand} vs competitors pricing comparison", "type": "commercial"}},
        {{"text": "How does {category} work?", "type": "informational"}}
    ]
    """

    try:
        response = completion(
            model="groq/llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(content)
        
        # Extract prompts array from response
        if isinstance(data, list):
            prompts = data
        elif isinstance(data, dict) and "prompts" in data:
            prompts = data["prompts"]
        else:
            # Try to find any array in the response
            for value in data.values():
                if isinstance(value, list):
                    prompts = value
                    break
            else:
                prompts = []
        
        return prompts
    except Exception as e:
        print(f"Error generating prompts: {e}")
        # Fallback simplistic generation if LLM fails completely
        return [{"text": f"Review of {brand}", "type": "commercial"}] * 10
