import json
import os
import re
from litellm import completion
from urllib.parse import urlparse

class Analyzer:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        if not self.groq_key:
            raise ValueError("GROQ_API_KEY is not set in environment")
    
    def extract_urls(self, text: str) -> list[str]:
        """Extract URLs from text using regex"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        return re.findall(url_pattern, text)
    
    def extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace('www.', '')
        except ValueError:
            return url
    
    async def analyze_result(self, text_content: str, brand_name: str) -> dict:
        """
        Enhanced analysis: Detects target brand, competitors, and URLs.
        Returns comprehensive JSON for advanced metrics.
        """
        # Extract URLs first (for reference)
        found_urls = self.extract_urls(text_content)

        
        prompt = f"""
You are a Brand Visibility Analyst.

Target Brand: "{brand_name}"

Analyze this AI response and extract:
1. Target brand mention (rank, sentiment)
2. ALL competitor brands mentioned
3. ALL URLs/citations mentioned
4. Determine if URLs belong to target brand

AI Response:
{text_content}

Return JSON ONLY:
{{
    "target_brand": {{
        "is_mentioned": true/false,
        "rank": int (0 if not mentioned, 1 if first, 2 if second, etc.),
        "sentiment": float (0.0-1.0),
        "summary": "brief explanation"
    }},
    "competitors": [
        {{"name": "CompetitorName", "rank": 2, "sentiment": 0.7}}
    ],
    "cited_urls": [
        {{"url": "https://example.com", "is_target_brand": true/false}}
    ]
}}

Instructions:
- For competitors: Only include OTHER brands mentioned (not the target brand)
- For rank: 1=first mentioned, 2=second, etc. 0=not mentioned
- For URLs: Check if domain belongs to target brand
- If no competitors/URLs found, return empty arrays
"""
        
        try:
            response = completion(
                model="groq/llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                api_key=self.groq_key,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1000  # Increased for more complex response
            )
            content = response.choices[0].message.content
            analysis = json.loads(content)
            
            # Fallback: If LLM didn't find URLs but we did with regex, add them
            if not analysis.get("cited_urls") and found_urls:
                analysis["cited_urls"] = [
                    {"url": url, "is_target_brand": False} for url in found_urls[:10]
                ]
            
            return analysis
            
        except Exception as e:
            print(f"[Analyzer] Error: {e}")
            return {
                "target_brand": {
                    "is_mentioned": False,
                    "rank": 0,
                    "sentiment": 0.5,
                    "summary": "Error during analysis"
                },
                "competitors": [],
                "cited_urls": []
            }
