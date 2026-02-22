import asyncio
from arq import Worker
from app.core.queue import redis_settings
from app.core.db import async_session_factory
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.campaign import Prompt
from sqlmodel import select

async def startup(ctx):
    print("Worker starting up...")
    ctx["session_factory"] = async_session_factory

async def shutdown(ctx):
    print("Worker shutting down...")


# from app.services.crawler import Crawler # Deprecated
from app.services.executor import Executor
from app.models.result import Result
from app.services.analyzer import Analyzer
from app.models.campaign import Campaign

import random

async def process_prompt_job(ctx, prompt_id: int):
    """
    Core job: Fetch Prompt -> Execute AI (API) -> Analyze -> Save Result
    """
    print(f"[Worker] Processing Prompt ID: {prompt_id}")
    
    async with ctx["session_factory"]() as session:
        prompt = await session.get(Prompt, prompt_id)
        if not prompt:
            print(f"Prompt {prompt_id} not found")
            return

        # 1. Execute (Fetch Response from AI)
        executor = Executor()
        # Using Groq for better rate limits (30 RPM, 14,400 RPD)
        target_platform = "groq" 
        
        try:
            response_text = await executor.fetch_response(prompt.text, platform=target_platform)
            # Rate limiting: Wait 2 seconds to respect Groq's 30 RPM limit
            # 30 requests/minute = 1 request every 2 seconds
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[Worker] Execution Failed: {e}")
            return


        # 2. Analyze (Judge the response)
        print(f"[Worker] Analyzing response for {prompt_id}...")
        try:
            # Check Campaign for Brand Name
            campaign = await session.get(Campaign, prompt.campaign_id)
            brand_name = campaign.brand_name if campaign else "Unknown"

            analyzer = Analyzer()
            # Analyze the text directly - now returns enhanced data
            analysis = await analyzer.analyze_result(response_text, brand_name)
            
            # Extract target brand data from new structure
            target_brand = analysis.get("target_brand", {})
            
            # 3. Save Result
            result = Result(
                prompt_id=prompt_id,
                platform=target_platform,
                response_text=response_text,
                rank=target_brand.get("rank", 0),
                sentiment_score=target_brand.get("sentiment", 0.5),
                analysis_json=analysis
            )
            session.add(result)
            await session.commit()
            await session.refresh(result)  # Get the ID
            
            print(f"Result saved for prompt {prompt_id}: Rank {result.rank}, Sentiment {result.sentiment_score}")
            
            # 4. Save Competitor Mentions
            from app.models.competitor_mention import CompetitorMention
            competitors = analysis.get("competitors", [])
            for comp in competitors:
                competitor = CompetitorMention(
                    result_id=result.id,
                    brand_name=comp.get("name", "Unknown"),
                    rank=comp.get("rank"),
                    sentiment_score=comp.get("sentiment")
                )
                session.add(competitor)
            
            # 5. Save Cited URLs
            from app.models.cited_url import CitedUrl
            cited_urls = analysis.get("cited_urls", [])
            for url_data in cited_urls:
                cited = CitedUrl(
                    result_id=result.id,
                    url=url_data.get("url", ""),
                    domain=analyzer.extract_domain(url_data.get("url", "")),
                    is_target_brand=url_data.get("is_target_brand", False)
                )
                session.add(cited)
            
            await session.commit()
            print(f"[Worker] Saved {len(competitors)} competitors and {len(cited_urls)} URLs")
            
        except Exception as e:
            print(f"Analysis Failed: {e}")
            import traceback
            traceback.print_exc()




class WorkerSettings:
    functions = [process_prompt_job]
    redis_settings = redis_settings
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 1  # Process one job at a time to respect rate limits
