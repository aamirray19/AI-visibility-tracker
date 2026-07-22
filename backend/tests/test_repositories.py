from app.db.repositories.companies import CompanyRepository
from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.evaluations import EvaluationRepository
from app.db.repositories.job_runs import JobRunRepository
from app.db.repositories.mentions import MentionRepository
from app.db.repositories.metrics import ScanMetricsRepository
from app.db.repositories.profiles import CompanyProfileRepository
from app.db.repositories.prompts import PromptRepository
from app.db.repositories.responses import AIResponseRepository
from app.db.repositories.scans import ScanRepository


async def test_full_repository_round_trip(db_session):
    """One test walks the whole FK chain: every repository gets a create + get-back
    round trip, in the order the schema's foreign keys require."""
    companies = CompanyRepository(db_session)
    scans = ScanRepository(db_session)
    profiles = CompanyProfileRepository(db_session)
    entities = ScanEntityRepository(db_session)
    prompts = PromptRepository(db_session)
    responses = AIResponseRepository(db_session)
    evaluations = EvaluationRepository(db_session)
    mentions = MentionRepository(db_session)
    metrics = ScanMetricsRepository(db_session)
    job_runs = JobRunRepository(db_session)

    company = await companies.create(name="Acme Corp", name_norm="acme", domain="acme.com")
    assert (await companies.get(company.id)).domain == "acme.com"

    scan = await scans.create(company_id=company.id)
    assert (await scans.get(scan.id)).status == "created"

    profile = await profiles.create(scan_id=scan.id, version=1, source="ai_generated", industry="SaaS")
    assert (await profiles.get(profile.id)).industry == "SaaS"

    entity = await entities.create(scan_id=scan.id, name="Acme Corp", name_norm="acme", is_target=True)
    assert (await entities.get(entity.id)).is_target is True

    prompt = await prompts.create(
        scan_id=scan.id, text="Best tools for X?", category="commercial", dedupe_hash="abc123"
    )
    assert (await prompts.get(prompt.id)).category == "commercial"

    response = await responses.create(
        scan_id=scan.id,
        prompt_id=prompt.id,
        provider="google_ai_studio",
        model="gemma-4-31b-it",
        status="success",
        raw_response="Acme is great.",
    )
    assert (await responses.get(response.id)).status == "success"

    evaluation = await evaluations.create(
        scan_id=scan.id, response_id=response.id, sentiment="positive", target_mentioned=True
    )
    assert (await evaluations.get(evaluation.id)).sentiment == "positive"

    mention = await mentions.create(
        scan_id=scan.id,
        evaluation_id=evaluation.id,
        response_id=response.id,
        entity_id=entity.id,
        raw_name="Acme Corp",
        is_target=True,
    )
    assert (await mentions.get(mention.id)).raw_name == "Acme Corp"

    scan_metrics = await metrics.create(scan_id=scan.id, metrics={"summary": {"ai_visibility": 42.0}})
    assert (await metrics.get(scan.id)).metrics["summary"]["ai_visibility"] == 42.0

    job_run = await job_runs.create(scan_id=scan.id, job_name="enrich_company", status="success")
    assert (await job_runs.get(job_run.id)).job_name == "enrich_company"
    assert scan_metrics.scan_id == scan.id
