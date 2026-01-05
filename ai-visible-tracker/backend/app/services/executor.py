import os
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type
from litellm import completion

class Executor:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        if not self.groq_key:
            raise ValueError("GROQ_API_KEY is not set in environment")

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(5)
    )
    async def fetch_response(self, prompt: str, platform: str = "groq") -> str:
        """
        Fetches a response from Groq AI (Llama 3.3 70B).
        Retries automatically on failure (Rate Limits).
        """
        if platform != "groq":
            raise ValueError(f"Only 'groq' platform is supported, got: {platform}")

        model = "groq/llama-3.3-70b-versatile"
        
        print(f"[Executor] Calling Groq for prompt: {prompt[:30]}...")
        
        # Act as a User asking the AI
        messages = [{"role": "user", "content": prompt}]
        
        response = completion(
            model=model,
            messages=messages,
            api_key=self.groq_key
        )
        
        return response.choices[0].message.content
