"""Reusable full-scan fixture (§20.1 test data): seeds company -> scan ->
profile -> entities -> prompts -> responses -> evaluations -> mentions ->
scan_metrics. Built once here for Phase 11's dashboard/prompt-explorer
tests; reused as-is by Phase 21's end-to-end test."""

from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.evaluations import EvaluationRepository
from app.db.repositories.mentions import MentionRepository
from app.db.repositories.metrics import ScanMetricsRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.prompts import PromptRepository
from app.db.repositories.responses import AIResponseRepository
from app.db.repositories.scans import ScanRepository
from app.services import aggregation
from app.services.onboarding import upsert_company

CATEGORIES = ("informational", "commercial", "competitor_discovery", "product_specific")
PROVIDERS = ("google_ai_studio", "groq")


async def seed_full_scan(db_session, *, status: str = "completed", brand_only: bool = False):
    """Seeds one complete, realistic scan and returns it, with real
    scan_metrics computed via aggregation.compute_metrics -- so tests built
    on this fixture exercise the real read path against real aggregation
    output, not hand-crafted metrics."""
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, status=status, brand_only=brand_only)

    profiles = CompanyProfileRepository(db_session)
    await profiles.create(
        scan_id=scan.id,
        version=3,
        source="ai_verified",
        industry="SaaS",
        aliases=["Acme Co"],
        products=[{"name": "Acme Board"}],
        competitors=[] if brand_only else [{"name": "Globex", "domain": "globex.com"}],
    )

    entities = ScanEntityRepository(db_session)
    target = await entities.create(
        scan_id=scan.id, name="Acme", name_norm="acme", domain="acme.com", is_target=True, aliases=["Acme Co"]
    )
    competitor = None
    if not brand_only:
        competitor = await entities.create(
            scan_id=scan.id, name="Globex", name_norm="globex", domain="globex.com", is_target=False, aliases=[]
        )

    prompts = PromptRepository(db_session)
    responses = AIResponseRepository(db_session)
    evaluations = EvaluationRepository(db_session)
    mentions = MentionRepository(db_session)

    for i, category in enumerate(CATEGORIES):
        prompt = await prompts.create(
            scan_id=scan.id, text=f"{category} prompt {i}", category=category, dedupe_hash=f"hash{i}"
        )
        for provider in PROVIDERS:
            target_mentioned = i % 2 == 0
            response = await responses.create(
                scan_id=scan.id,
                prompt_id=prompt.id,
                provider=provider,
                model="gemma-4-31b-it" if provider == "google_ai_studio" else "openai/gpt-oss-120b",
                status="success",
                raw_response=f"Discussion mentioning {'Acme' if target_mentioned else 'nothing relevant'}.",
                citations=[{"url": "https://g2.com/x", "domain": "g2.com"}] if provider == "groq" else [],
            )
            mentioned_companies = []
            if target_mentioned:
                mentioned_companies = ["Acme"] if brand_only else ["Acme", "Globex"]
            evaluation = await evaluations.create(
                scan_id=scan.id,
                response_id=response.id,
                sentiment="positive" if target_mentioned else None,
                target_mentioned=target_mentioned,
                recommended=target_mentioned,
                rank_position=1 if target_mentioned else None,
                mentioned_companies=mentioned_companies,
                evaluator_model="llama-3.3-70b-versatile",
                evaluator_pool="eval_a" if provider == "google_ai_studio" else "eval_b",
            )
            if target_mentioned:
                await mentions.create(
                    scan_id=scan.id, evaluation_id=evaluation.id, response_id=response.id,
                    entity_id=target.id, raw_name="Acme", is_target=True, rank_position=1, sentiment="positive",
                )
                if competitor:
                    await mentions.create(
                        scan_id=scan.id, evaluation_id=evaluation.id, response_id=response.id,
                        entity_id=competitor.id, raw_name="Globex", is_target=False,
                    )

    await db_session.commit()

    metrics = await aggregation.compute_metrics(db_session, scan.id)
    metrics["brand_only"] = brand_only
    metrics_repo = ScanMetricsRepository(db_session)
    await metrics_repo.create(scan_id=scan.id, metrics=metrics)
    await db_session.commit()

    return scan
