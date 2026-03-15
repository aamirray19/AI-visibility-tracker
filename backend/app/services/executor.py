import asyncio
import logging
from abc import ABC, abstractmethod
from groq import AsyncGroq
from google import genai
from google.genai import types as genai_types
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelProvider(ABC):
    """Abstract interface all model providers must implement."""

    name: str

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate response from model."""
        pass


class GroqProvider(ModelProvider):
    """GPT-OSS provider via Groq."""

    name = "gpt"

    def __init__(self, api_key: str):
        self.client = AsyncGroq(api_key=api_key)

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(3),
    )
    async def generate(self, prompt: str) -> str:
        logger.debug("Calling GPT-OSS-120B via Groq")

        response = await self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.choices[0].message.content or ""
        logger.debug("GPT response received: %d chars", len(text))
        return text



class GemmaProvider(ModelProvider):
    """Gemma provider via Google AI Studio."""

    name = "gemma"

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(3),
    )
    async def generate(self, prompt: str) -> str:

        logger.debug("Calling Gemma3:27B via Google AI Studio")

        config = genai_types.GenerateContentConfig( 
            temperature=0.7,
        )

        loop = asyncio.get_running_loop()

        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model="gemma-3-27b-it",
                contents=prompt,
                config=config,
            ),
        )

        text = response.text or ""
        logger.debug("Gemma response received: %d chars", len(text))
        return text



class Executor:
    """
    Executes prompts across multiple AI models in parallel.
    Depends only on the ModelProvider abstraction.
    """

    def __init__(self, providers: list[ModelProvider]):
        self.providers = providers

    async def fetch_all_responses(self, prompt: str) -> dict[str, str]:
        """Fetch responses from all providers in parallel."""

        logger.info(
            "Fetching responses for prompt (len=%d) from %d models",
            len(prompt),
            len(self.providers),
        )

        tasks = {
            provider.name: asyncio.create_task(provider.generate(prompt))
            for provider in self.providers
        }

        responses = await asyncio.gather(
            *tasks.values(),
            return_exceptions=True,
        )

        results: dict[str, str] = {}

        for name, response in zip(tasks.keys(), responses):

            if isinstance(response, Exception):
                logger.error("%s fetch failed: %s", name, response, exc_info=True)
                continue

            results[name] = response

        logger.info(
            "Fetched responses from %d/%d models",
            len(results),
            len(self.providers),
        )

        return results
