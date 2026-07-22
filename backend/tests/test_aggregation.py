from app.db.repositories.entities import ScanEntityRepository
from app.db.repositories.evaluations import EvaluationRepository
from app.db.repositories.mentions import MentionRepository
from app.db.repositories.prompts import PromptRepository
from app.db.repositories.responses import AIResponseRepository
from app.db.repositories.scans import ScanRepository
from app.services import aggregation
from app.services.onboarding import upsert_company

# Fixture: 4 evaluated responses across 2 providers x 2 categories.
#   r1 google_ai_studio/informational: Acme mentioned, positive, recommended, rank=1. Mentions: Acme(target), Globex.
#   r2 google_ai_studio/commercial:    Acme not mentioned. Mentions: Globex.
#   r3 groq/informational:             Acme mentioned, negative, not recommended, no rank. Mentions: Acme.
#   r4 groq/commercial:                Acme mentioned, neutral, recommended, rank=2. Mentions: Acme, Initech (discovered).
#
# Hand-computed expectations documented inline on each assertion.


async def _seed(db_session):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    scan = await scans.create(company_id=company.id, brand_only=False)

    entities = ScanEntityRepository(db_session)
    acme = await entities.create(scan_id=scan.id, name="Acme", name_norm="acme", is_target=True, aliases=[])
    globex = await entities.create(scan_id=scan.id, name="Globex", name_norm="globex", is_target=False, aliases=[])

    prompts = PromptRepository(db_session)
    p_info = await prompts.create(scan_id=scan.id, text="informational prompt", category="informational", dedupe_hash="h1")
    p_comm = await prompts.create(scan_id=scan.id, text="commercial prompt", category="commercial", dedupe_hash="h2")

    responses = AIResponseRepository(db_session)
    evaluations = EvaluationRepository(db_session)
    mentions = MentionRepository(db_session)

    r1 = await responses.create(
        scan_id=scan.id, prompt_id=p_info.id, provider="google_ai_studio", model="gemma-4-31b-it", status="success",
        citations=[{"url": "https://g2.com/a", "domain": "g2.com"}],
    )
    e1 = await evaluations.create(
        scan_id=scan.id, response_id=r1.id, sentiment="positive", target_mentioned=True, recommended=True,
        rank_position=1,
    )
    await mentions.create(scan_id=scan.id, evaluation_id=e1.id, response_id=r1.id, entity_id=acme.id, raw_name="Acme", is_target=True, rank_position=1, sentiment="positive")
    await mentions.create(scan_id=scan.id, evaluation_id=e1.id, response_id=r1.id, entity_id=globex.id, raw_name="Globex", is_target=False)

    r2 = await responses.create(
        scan_id=scan.id, prompt_id=p_comm.id, provider="google_ai_studio", model="gemma-4-31b-it", status="success",
    )
    e2 = await evaluations.create(scan_id=scan.id, response_id=r2.id, target_mentioned=False, recommended=False)
    await mentions.create(scan_id=scan.id, evaluation_id=e2.id, response_id=r2.id, entity_id=globex.id, raw_name="Globex", is_target=False)

    r3 = await responses.create(
        scan_id=scan.id, prompt_id=p_info.id, provider="groq", model="openai/gpt-oss-120b", status="success",
        citations=[{"url": "https://g2.com/b", "domain": "g2.com"}],
    )
    e3 = await evaluations.create(
        scan_id=scan.id, response_id=r3.id, sentiment="negative", target_mentioned=True, recommended=False,
    )
    await mentions.create(scan_id=scan.id, evaluation_id=e3.id, response_id=r3.id, entity_id=acme.id, raw_name="Acme", is_target=True, sentiment="negative")

    r4 = await responses.create(
        scan_id=scan.id, prompt_id=p_comm.id, provider="groq", model="openai/gpt-oss-120b", status="success",
    )
    e4 = await evaluations.create(
        scan_id=scan.id, response_id=r4.id, sentiment="neutral", target_mentioned=True, recommended=True,
        rank_position=2,
    )
    await mentions.create(scan_id=scan.id, evaluation_id=e4.id, response_id=r4.id, entity_id=acme.id, raw_name="Acme", is_target=True, rank_position=2, sentiment="neutral")
    await mentions.create(scan_id=scan.id, evaluation_id=e4.id, response_id=r4.id, entity_id=None, raw_name="Initech", is_target=False)

    await db_session.commit()
    return scan


async def test_compute_metrics_summary(db_session):
    scan = await _seed(db_session)
    metrics = await aggregation.compute_metrics(db_session, scan.id)
    summary = metrics["summary"]

    assert summary["responses_total"] == 4
    assert summary["responses_evaluated"] == 4
    assert summary["ai_visibility"] == 75.0  # 3/4 mentioned
    assert summary["recommendation_rate"] == 50.0  # 2/4 recommended
    assert round(summary["recommendation_rate_when_mentioned"], 1) == 66.7  # 2/3
    assert summary["share_of_voice"] == 50.0  # 3 target mentions / 6 total mentions
    assert summary["net_sentiment"] == 0.0  # 1 positive - 1 negative over 3 mentioned


async def test_compute_metrics_leaderboard(db_session):
    scan = await _seed(db_session)
    metrics = await aggregation.compute_metrics(db_session, scan.id)
    by_name = {row["name"]: row for row in metrics["leaderboard"]}

    acme = by_name["Acme"]
    assert acme["is_target"] is True
    assert acme["mentions"] == 3
    assert acme["positive"] == 1
    assert acme["neutral"] == 1
    assert acme["negative"] == 1
    assert acme["rank_count"] == 2
    assert acme["avg_rank"] == 1.5

    globex = by_name["Globex"]
    assert globex["mentions"] == 2
    assert globex["is_target"] is False


async def test_compute_metrics_discovered_companies(db_session):
    scan = await _seed(db_session)
    metrics = await aggregation.compute_metrics(db_session, scan.id)
    assert metrics["discovered"] == [{"name": "Initech", "mentions": 1}]


async def test_compute_metrics_by_category(db_session):
    scan = await _seed(db_session)
    metrics = await aggregation.compute_metrics(db_session, scan.id)
    by_cat = {row["category"]: row for row in metrics["by_category"]}
    assert by_cat["informational"] == {"category": "informational", "visibility": 100.0, "n": 2}
    assert by_cat["commercial"] == {"category": "commercial", "visibility": 50.0, "n": 2}


async def test_compute_metrics_by_provider(db_session):
    scan = await _seed(db_session)
    metrics = await aggregation.compute_metrics(db_session, scan.id)
    by_prov = {row["provider"]: row for row in metrics["by_provider"]}
    assert by_prov["google_ai_studio"]["visibility"] == 50.0
    assert by_prov["google_ai_studio"]["success_rate"] == 1.0
    assert by_prov["groq"]["visibility"] == 100.0
    assert by_prov["groq"]["success_rate"] == 1.0


async def test_compute_metrics_rank_distribution(db_session):
    scan = await _seed(db_session)
    metrics = await aggregation.compute_metrics(db_session, scan.id)
    assert metrics["rank_distribution"] == {"1": 1, "2": 1, "3": 0, "4": 0, "5plus": 0}


async def test_compute_metrics_top_sources(db_session):
    scan = await _seed(db_session)
    metrics = await aggregation.compute_metrics(db_session, scan.id)
    assert metrics["top_sources"] == [{"domain": "g2.com", "responses": 2}]


async def test_compute_metrics_excludes_provider(db_session):
    scan = await _seed(db_session)
    metrics = await aggregation.compute_metrics(db_session, scan.id, excluded_providers={"groq"})
    assert metrics["summary"]["responses_total"] == 2
    assert {row["provider"] for row in metrics["by_provider"]} == {"google_ai_studio"}


async def test_provider_rates_computes_ratio(db_session):
    scan = await _seed(db_session)
    rates = await aggregation.provider_rates(db_session, scan.id)
    assert rates == {"google_ai_studio": 1.0, "groq": 1.0}


# --- decide_outcome: §13.2 decision table -----------------------------------


def test_decide_outcome_all_above_threshold_completes():
    status, excluded, detail = aggregation.decide_outcome({"google_ai_studio": 0.98, "groq": 0.96})
    assert status == "completed"
    assert excluded == set()
    assert detail is None


def test_decide_outcome_one_provider_unavailable_completes_with_gaps_excluding_it():
    status, excluded, _ = aggregation.decide_outcome({"google_ai_studio": 0.98, "groq": 0.0})
    assert status == "completed_with_gaps"
    assert excluded == {"groq"}


def test_decide_outcome_participating_provider_between_70_and_95_completes_with_gaps():
    status, excluded, _ = aggregation.decide_outcome({"google_ai_studio": 0.98, "groq": 0.80})
    assert status == "completed_with_gaps"
    assert excluded == set()


def test_decide_outcome_participating_provider_below_70_fails():
    status, excluded, _ = aggregation.decide_outcome({"google_ai_studio": 0.98, "groq": 0.50})
    assert status == "failed"


def test_decide_outcome_every_provider_unavailable_fails():
    status, _, _ = aggregation.decide_outcome({"google_ai_studio": 0.0, "groq": 0.0})
    assert status == "failed"


def test_decide_outcome_no_providers_fails():
    status, _, _ = aggregation.decide_outcome({})
    assert status == "failed"
