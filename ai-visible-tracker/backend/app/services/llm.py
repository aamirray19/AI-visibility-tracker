import os
from litellm import completion
import json

async def generate_brand_list(category: str) -> list[str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")

    prompt = f"""
    List the top 15 most prominent companies/brands in the product category: "{category}".
    Return ONLY a raw JSON array of strings. Do not include markdown formatting or explanation.
    Example: ["Nike", "Adidas", "Puma"]
    """

    try:
        response = completion(
            model="groq/llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        # Parse the JSON response
        data = json.loads(content)
        
        # Handle different possible response formats
        if isinstance(data, list):
            brands = data
        elif isinstance(data, dict) and "brands" in data:
            brands = data["brands"]
        else:
            # Try to extract first array value
            brands = list(data.values())[0] if data else []
            
        return brands[:15]  # Ensure max 15 brands
    except Exception as e:
        print(f"Groq Error: {e}")
        # Fallback for dev/debug if LLM fails
        return ["Error generating brands", "Check API Key"]
