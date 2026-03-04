import os
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type
from litellm import completion

SUPPORTED_PLATFORMS = [
    "groq_gpt_oss_120b",
    "google_gemma3_27b",
]


PLATFORM_CONFIG = {
    "groq_gpt_oss_120b": {
        "model": "groq/openai/gpt-oss-120b",
        "api_key_env": "GROQ_API_KEY",
        # Groq supports built-in web search for supported models via tools.
        "tools": [{"type": "web_search"}],
    },
    "google_gemma3_27b": {
        "model": "gemini/gemma-3-27b-it",
        "api_key_env": "GOOGLE_API_KEY",
        # Google AI Studio built-in Google Search grounding.
        "tools": [{"googleSearch": {}}],
    },
}

class Executor:
    def __init__(self):
        self.api_keys = {
            platform: os.getenv(config["api_key_env"])
            for platform, config in PLATFORM_CONFIG.items()
        }

        missing_keys = [
            PLATFORM_CONFIG[platform]["api_key_env"]
            for platform, key in self.api_keys.items()
            if not key
        ]
        if missing_keys:
            raise ValueError(f"Missing required API keys: {', '.join(missing_keys)}")

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(5)
    )
    async def fetch_response(self, prompt: str, platform: str = "groq_gpt_oss_120b") -> str:
        """
        Fetches a response from supported providers/models.
        Retries automatically on failure (Rate Limits).
        """
        if platform not in PLATFORM_CONFIG:
            raise ValueError(f"Unsupported platform: {platform}")

        config = PLATFORM_CONFIG[platform]
        model = config["model"]
        api_key = self.api_keys[platform]
        tools = config["tools"]
        
        print(f"[Executor] Calling {platform} for prompt: {prompt[:30]}...")
        
        # Act as a User asking the AI
        messages = [{"role": "user", "content": prompt}]
        
        response = completion(
            model=model,
            messages=messages,
            api_key=api_key,
            tools=tools,
        )
        
        return response.choices[0].message.content
