import asyncio
import logging
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.core.db import async_session_factory
from app.core.config import settings
from app.core.queue import redis_settings
from app.models.campaign import Campaign, Prompt
from app.models.result import Result
from app.models.cited_url import CitedUrl
from app.models.competitor_mention import CompetitorMention
from app.services.executor import Executor
from app.services.executor import GroqProvider, GemmaProvider
from app.services.analyzer import Analyzer

logger = logging.getLogger(__name__)

executor: Executor | None = None
analyzer: Analyzer | None = None
analysis_semaphore = asyncio.Semaphore(10)


async def startup(ctx):
    redis = ctx["redis"]

    # Flush previous queued jobs
    await redis.flushdb()

    global executor, analyzer

    executor = Executor([
        GroqProvider(settings.GROQ_API_KEY),
        GemmaProvider(settings.GOOGLE_AI_API_KEY),
    ])

    analyzer = Analyzer()

    logger.info("Worker services initialized and Redis queue flushed")



# Main job

async def process_prompt_job(ctx, prompt_id: int):
    logger.info("Processing prompt job: prompt_id=%d", prompt_id)

    async with async_session_factory() as session:

        prompt = await session.get(Prompt, prompt_id)

        if not prompt:
            logger.warning("Prompt %d not found — skipping", prompt_id)
            return

        if prompt.status == "COMPLETED":
            logger.info("Prompt %d already completed — skipping", prompt_id)
            return

        campaign = await session.get(Campaign, prompt.campaign_id)

        if not campaign:
            logger.warning("Campaign not found for prompt %d — skipping", prompt_id)
            return

        brand_name = campaign.brand_name

        prompt.status = "PROCESSING"
        await session.commit()

    #Execute model calls with retry

    responses = None

    for attempt in range(3):
        try:
            responses = await executor.fetch_all_responses(prompt.text)
            break
        except Exception as e:

            if attempt == 2:
                logger.error(
                    "Execution failed for prompt %d after retries: %s",
                    prompt_id,
                    e,
                    exc_info=True,
                )

                async with async_session_factory() as session:
                    prompt = await session.get(Prompt, prompt_id)
                    prompt.status = "FAILED"
                    await session.commit()

                return

            await asyncio.sleep(2 ** attempt)

    await asyncio.sleep(settings.RATE_LIMIT_SLEEP_SECONDS)

    #Process results in parallel

    tasks = []

    for platform, response_text in responses.items():

        tasks.append(
            _process_single_result(
                prompt_id=prompt_id,
                platform=platform,
                response_text=response_text,
                brand_name=brand_name,
            )
        )

    semaphore = asyncio.Semaphore(2)

    async def limited_task(task):
        async with semaphore:
            return await task

    results_success = await asyncio.gather(
        *[limited_task(t) for t in tasks]
    )
    success_count = sum(1 for r in results_success if r)

    #Mark prompt completed/partial/failed

    async with async_session_factory() as session:

        prompt = await session.get(Prompt, prompt_id)

        if prompt:
            if success_count > 0 and success_count == len(responses):
                prompt.status = "COMPLETED"
            elif success_count > 0:
                prompt.status = "PARTIAL"
            else:
                prompt.status = "FAILED"
            await session.commit()

    logger.info(
        "Prompt %d processed: %d/%d model(s) succeeded",
        prompt_id,
        success_count,
        len(responses) if responses else 0,
    )

    if success_count == 0:
        raise Exception(f"Failed to process any results for prompt {prompt_id}. Throwing to trigger ARQ retry.")


#Single result processor

async def _process_single_result(
    prompt_id: int,
    platform: str,
    response_text: str,
    brand_name: str,
) -> bool:
    """
    Saves raw response first, then performs analysis.
    If analysis fails, raw response remains persisted.
    Returns True if the raw response was saved successfully, False otherwise.
    """

    if not response_text or not response_text.strip():

        logger.warning(
            "Empty response from %s for prompt %d",
            platform,
            prompt_id,
        )
        return False

    response_text = response_text[:10000]

    async with async_session_factory() as session:

        #Save raw response

        result = Result(
            prompt_id=prompt_id,
            platform=platform,
            response_text=response_text,
            rank=None,
            brand_mentioned=False,
            sentiment_score=None,
            mention_context=None,
        )

        try:
            session.add(result)
            await session.commit()
            await session.refresh(result)
        except Exception as e:
            logger.error("Failed to save raw response for platform %s: %s", platform, e)
            return False

        logger.info(
            "Saved raw response for prompt %d platform=%s result_id=%d",
            prompt_id,
            platform,
            result.id,
        )

        #Run analysis with concurrency limit

        try:

            async with analysis_semaphore:

                analysis = await asyncio.wait_for(
                    analyzer.analyze_result(response_text, brand_name),
                    timeout=30,
                )

        except Exception as e:

            logger.error(
                "Analysis failed for result %d prompt %d platform=%s: %s",
                result.id,
                prompt_id,
                platform,
                e,
                exc_info=True,
            )
            return True 

        target = analysis.get("target_brand", {})
        competitors_data = analysis.get("competitors", [])

        #Update result with analysis

        result.rank = target.get("rank")
        result.brand_mentioned = bool(target.get("is_mentioned", False))
        result.sentiment_score = target.get("sentiment_score")

        mention_context = target.get("mention_context")
        result.mention_context = mention_context[:500] if mention_context else None

        #Prepare batch inserts

        urls = []
        mentions = []

        for url_data in analysis.get("cited_urls", []):
            url = url_data.get("url")
            if url:
                urls.append(
                    CitedUrl(
                        result_id=result.id,
                        url=str(url)[:500],
                        domain=str(url_data.get("domain", ""))[:255],
                        is_target_brand=bool(url_data.get("is_target_brand", False)),
                    )
                )

        for comp in analysis.get("competitors", []):
            name = comp.get("name")
            if name:
                mentions.append(
                    CompetitorMention(
                        result_id=result.id,
                        brand_name=str(name)[:255],
                        rank=comp.get("rank"),
                        sentiment_score=comp.get("sentiment_score"),
                    )
                )

        session.add_all(urls)
        session.add_all(mentions)

        await session.commit()

        logger.info(
            "Analysis complete for result %d mentioned=%s rank=%s urls=%d competitors=%d",
            result.id,
            result.brand_mentioned,
            result.rank,
            len(urls),
            len(mentions),
        )
        return True


#Worker settings
class WorkerSettings:
    functions = [process_prompt_job]
    redis_settings = redis_settings
    max_jobs = settings.WORKER_MAX_JOBS
    job_timeout = 300
    max_tries = 1    
    on_startup = startup
    on_shutdown = None