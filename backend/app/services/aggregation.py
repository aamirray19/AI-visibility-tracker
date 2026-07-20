import uuid
from collections import defaultdict

from sqlalchemy import func, select

from app.db.models import AIResponse, Evaluation, Mention, Prompt, ScanEntity
from app.services.entity_resolution import collapse_discovered_names

RANK_BUCKETS = ("1", "2", "3", "4", "5plus")


async def provider_rates(session, scan_id: uuid.UUID) -> dict[str, float]:
    """§13.2: provider_rate(p) = evaluated_successfully(p) / attempted(p)."""
    attempted_stmt = (
        select(AIResponse.provider, func.count()).where(AIResponse.scan_id == scan_id).group_by(AIResponse.provider)
    )
    attempted = dict((await session.execute(attempted_stmt)).all())

    evaluated_stmt = (
        select(AIResponse.provider, func.count())
        .join(Evaluation, Evaluation.response_id == AIResponse.id)
        .where(AIResponse.scan_id == scan_id, AIResponse.status == "success")
        .group_by(AIResponse.provider)
    )
    evaluated_successfully = dict((await session.execute(evaluated_stmt)).all())

    return {
        provider: (evaluated_successfully.get(provider, 0) / count if count else 0.0)
        for provider, count in attempted.items()
    }


def decide_outcome(rates: dict[str, float]) -> tuple[str, set[str], str | None]:
    """§13.2's partial-results decision table. Returns (status, excluded_providers, banner_detail)."""
    if not rates:
        return "failed", set(), "no providers attempted"
    if all(r >= 0.95 for r in rates.values()):
        return "completed", set(), None

    unavailable = {p for p, r in rates.items() if r == 0.0}
    participating = {p: r for p, r in rates.items() if p not in unavailable}

    if not participating:
        return "failed", set(), "every provider unavailable"
    if any(r < 0.70 for r in participating.values()):
        return "failed", set(), "a participating provider fell below 0.70"
    if unavailable:
        return "completed_with_gaps", unavailable, f"{', '.join(sorted(unavailable))} unavailable"
    return "completed_with_gaps", set(), "some responses were lost"


async def compute_metrics(session, scan_id: uuid.UUID, *, excluded_providers: set[str] = frozenset()) -> dict:
    """§12: assembles the full scan_metrics.metrics JSON. R = ai_responses
    with status='success' AND an evaluation row exists -- never "attempted",
    since a provider timeout must not look like brand invisibility. A
    provider in `excluded_providers` (§13.2, entirely unavailable) is
    dropped from every metric, not counted as failure."""
    r_stmt = (
        select(
            AIResponse.id,
            AIResponse.provider,
            Prompt.category,
            Evaluation.target_mentioned,
            Evaluation.recommended,
            Evaluation.sentiment,
            Evaluation.rank_position,
        )
        .join(Evaluation, Evaluation.response_id == AIResponse.id)
        .join(Prompt, Prompt.id == AIResponse.prompt_id)
        .where(AIResponse.scan_id == scan_id, AIResponse.status == "success")
    )
    if excluded_providers:
        r_stmt = r_stmt.where(AIResponse.provider.notin_(excluded_providers))
    r_rows = (await session.execute(r_stmt)).all()
    n = len(r_rows)

    total_stmt = select(func.count()).select_from(AIResponse).where(AIResponse.scan_id == scan_id)
    if excluded_providers:
        total_stmt = total_stmt.where(AIResponse.provider.notin_(excluded_providers))
    responses_total = (await session.execute(total_stmt)).scalar_one()

    target_mentioned_count = sum(1 for row in r_rows if row.target_mentioned)
    recommended_count = sum(1 for row in r_rows if row.recommended)
    recommended_when_mentioned = sum(1 for row in r_rows if row.target_mentioned and row.recommended)

    ai_visibility = (target_mentioned_count / n * 100) if n else 0.0
    recommendation_rate = (recommended_count / n * 100) if n else 0.0
    recommendation_rate_when_mentioned = (
        (recommended_when_mentioned / target_mentioned_count * 100) if target_mentioned_count else 0.0
    )

    positive = sum(1 for row in r_rows if row.target_mentioned and row.sentiment == "positive")
    negative = sum(1 for row in r_rows if row.target_mentioned and row.sentiment == "negative")
    net_sentiment = ((positive - negative) / target_mentioned_count) if target_mentioned_count else 0.0

    mentions_stmt = (
        select(
            Mention.entity_id, Mention.raw_name, Mention.is_target, Mention.response_id,
            Mention.rank_position, Mention.sentiment,
        )
        .join(AIResponse, AIResponse.id == Mention.response_id)
        .where(Mention.scan_id == scan_id, AIResponse.status == "success")
    )
    if excluded_providers:
        mentions_stmt = mentions_stmt.where(AIResponse.provider.notin_(excluded_providers))
    mention_rows = (await session.execute(mentions_stmt)).all()

    # "counted once per response per entity" -- de-dup defensively even
    # though evaluate_response already writes at most one mention per
    # (response, entity).
    seen: set[tuple] = set()
    deduped = []
    for m in mention_rows:
        key = (m.response_id, m.entity_id or f"discovered:{m.raw_name.lower()}")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)

    all_entity_mentions = len(deduped)
    target_mentions = sum(1 for m in deduped if m.is_target)
    share_of_voice = (target_mentions / all_entity_mentions * 100) if all_entity_mentions else 0.0

    entity_rows = (await session.execute(select(ScanEntity).where(ScanEntity.scan_id == scan_id))).scalars().all()
    leaderboard = []
    for entity in entity_rows:
        entity_mentions = [m for m in deduped if m.entity_id == entity.id]
        ranks = [m.rank_position for m in entity_mentions if m.rank_position is not None]
        leaderboard.append(
            {
                "entity_id": str(entity.id),
                "name": entity.name,
                "is_target": entity.is_target,
                "mentions": len(entity_mentions),
                "positive": sum(1 for m in entity_mentions if m.sentiment == "positive"),
                "neutral": sum(1 for m in entity_mentions if m.sentiment == "neutral"),
                "negative": sum(1 for m in entity_mentions if m.sentiment == "negative"),
                "avg_rank": (sum(ranks) / len(ranks)) if ranks else None,
                "rank_count": len(ranks),
            }
        )

    discovered_raw = [m.raw_name for m in deduped if m.entity_id is None]
    canonical_map = collapse_discovered_names(discovered_raw) if discovered_raw else {}
    discovered_counts: dict[str, int] = defaultdict(int)
    for raw in discovered_raw:
        discovered_counts[canonical_map[raw]] += 1
    discovered = [
        {"name": name, "mentions": count}
        for name, count in sorted(discovered_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    category_totals: dict[str, list[bool]] = defaultdict(list)
    for row in r_rows:
        category_totals[row.category].append(row.target_mentioned)
    by_category = [
        {"category": cat, "visibility": round((sum(flags) / len(flags) * 100) if flags else 0.0, 1), "n": len(flags)}
        for cat, flags in category_totals.items()
    ]

    provider_totals: dict[str, list[bool]] = defaultdict(list)
    for row in r_rows:
        provider_totals[row.provider].append(row.target_mentioned)

    attempted_stmt = (
        select(AIResponse.provider, func.count()).where(AIResponse.scan_id == scan_id).group_by(AIResponse.provider)
    )
    attempted_by_provider = dict((await session.execute(attempted_stmt)).all())
    success_stmt = (
        select(AIResponse.provider, func.count())
        .where(AIResponse.scan_id == scan_id, AIResponse.status == "success")
        .group_by(AIResponse.provider)
    )
    success_by_provider = dict((await session.execute(success_stmt)).all())

    by_provider = [
        {
            "provider": provider,
            "visibility": round((sum(flags) / len(flags) * 100) if flags else 0.0, 1),
            "success_rate": round(
                success_by_provider.get(provider, 0) / attempted_by_provider[provider], 4
            )
            if attempted_by_provider.get(provider)
            else 0.0,
        }
        for provider, flags in provider_totals.items()
    ]

    rank_distribution = dict.fromkeys(RANK_BUCKETS, 0)
    for row in r_rows:
        if row.rank_position is None:
            continue
        bucket = str(row.rank_position) if row.rank_position < 5 else "5plus"
        if bucket not in rank_distribution:
            bucket = "5plus"
        rank_distribution[bucket] += 1

    top_sources = await _top_sources(session, scan_id, excluded_providers)

    return {
        "summary": {
            "ai_visibility": round(ai_visibility, 1),
            "recommendation_rate": round(recommendation_rate, 1),
            "recommendation_rate_when_mentioned": round(recommendation_rate_when_mentioned, 1),
            "share_of_voice": round(share_of_voice, 1),
            "net_sentiment": round(net_sentiment, 2),
            "responses_total": responses_total,
            "responses_evaluated": n,
        },
        "leaderboard": leaderboard,
        "discovered": discovered,
        "by_category": by_category,
        "by_provider": by_provider,
        "rank_distribution": rank_distribution,
        "top_sources": top_sources,
    }


async def _top_sources(session, scan_id: uuid.UUID, excluded_providers: set[str]) -> list[dict]:
    """§7.8, provider-filtered variant of GET /sources' SQL for §13.2's
    "surviving providers only" rule."""
    stmt = select(AIResponse.citations).where(AIResponse.scan_id == scan_id, AIResponse.status == "success")
    if excluded_providers:
        stmt = stmt.where(AIResponse.provider.notin_(excluded_providers))
    rows = (await session.execute(stmt)).scalars().all()

    counts: dict[str, int] = defaultdict(int)
    for citations in rows:
        for domain in {c.get("domain") for c in citations if c.get("domain")}:
            counts[domain] += 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:20]
    return [{"domain": domain, "responses": count} for domain, count in ranked]
