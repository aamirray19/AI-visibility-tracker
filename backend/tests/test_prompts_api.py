from tests.fixtures.full_scan import seed_full_scan


async def test_list_prompts_returns_all_by_default(client, db_session):
    scan = await seed_full_scan(db_session)

    response = await client.get(f"/api/v1/scans/{scan.id}/prompts")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4  # 4 prompts (one per category)
    assert len(body["items"]) == 4
    first = body["items"][0]
    assert set(first["providers"].keys()) == {"google_ai_studio", "groq"}


async def test_list_prompts_filters_by_category(client, db_session):
    scan = await seed_full_scan(db_session)

    response = await client.get(f"/api/v1/scans/{scan.id}/prompts", params={"category": "commercial"})
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "commercial"


async def test_list_prompts_filters_by_provider_and_mentioned(client, db_session):
    scan = await seed_full_scan(db_session)

    response = await client.get(
        f"/api/v1/scans/{scan.id}/prompts", params={"provider": "groq", "mentioned": "true"}
    )
    body = response.json()
    assert body["total"] > 0
    for item in body["items"]:
        assert item["providers"]["groq"]["target_mentioned"] is True


async def test_list_prompts_pagination(client, db_session):
    scan = await seed_full_scan(db_session)

    response = await client.get(f"/api/v1/scans/{scan.id}/prompts", params={"limit": 2, "offset": 0})
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 4

    response2 = await client.get(f"/api/v1/scans/{scan.id}/prompts", params={"limit": 2, "offset": 2})
    body2 = response2.json()
    assert len(body2["items"]) == 2
    assert {i["id"] for i in body["items"]}.isdisjoint({i["id"] for i in body2["items"]})


async def test_prompt_detail_returns_both_providers_with_citations_and_evaluation(client, db_session):
    scan = await seed_full_scan(db_session)
    listing = await client.get(f"/api/v1/scans/{scan.id}/prompts")
    prompt_id = listing.json()["items"][0]["id"]

    response = await client.get(f"/api/v1/scans/{scan.id}/prompts/{prompt_id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["responses"]) == 2
    providers = {r["provider"] for r in body["responses"]}
    assert providers == {"google_ai_studio", "groq"}
    groq_response = next(r for r in body["responses"] if r["provider"] == "groq")
    assert groq_response["citations"] == [{"url": "https://g2.com/x", "domain": "g2.com"}]
    assert groq_response["evaluation"] is not None


async def test_prompt_detail_404_for_unknown_prompt(client, db_session):
    scan = await seed_full_scan(db_session)
    response = await client.get(f"/api/v1/scans/{scan.id}/prompts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
