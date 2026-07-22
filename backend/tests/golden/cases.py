"""§20.2 golden set: hand-labeled (prompt, response) pairs with the sentiment
/ target_mentioned / recommended / rank_position a correct evaluator should
produce. Not a CI gate -- run manually via run_golden.py whenever the eval
prompt template, model, or provider changes (real tokens, non-deterministic
model)."""

CASES = [
    {
        "name": "clear_positive",
        "target_name": "Notion",
        "prompt_text": "What's a good all-in-one workspace tool for a small team?",
        "response_text": (
            "Notion is an excellent choice for small teams -- it combines docs, wikis, and "
            "lightweight project tracking in one clean interface, and the free tier is generous."
        ),
        "expected": {"sentiment": "positive", "target_mentioned": True, "recommended": True, "rank_position": None},
    },
    {
        "name": "clear_negative",
        "target_name": "Notion",
        "prompt_text": "Is Notion reliable for large teams?",
        "response_text": (
            "Notion tends to get sluggish once a workspace has thousands of pages, and several "
            "teams have reported sync issues and lost edits. I wouldn't recommend it at scale."
        ),
        "expected": {"sentiment": "negative", "target_mentioned": True, "recommended": False, "rank_position": None},
    },
    {
        "name": "clear_neutral",
        "target_name": "Notion",
        "prompt_text": "What is Notion?",
        "response_text": "Notion is a productivity application that combines notes, databases, and task boards.",
        "expected": {"sentiment": "neutral", "target_mentioned": True, "recommended": False, "rank_position": None},
    },
    {
        "name": "target_not_mentioned",
        "target_name": "Notion",
        "prompt_text": "Best tools for small-team project tracking?",
        "response_text": "Popular options include Trello, Asana, and Linear, depending on how technical your team is.",
        "expected": {"sentiment": None, "target_mentioned": False, "recommended": False, "rank_position": None},
    },
    {
        "name": "ranked_list_target_second",
        "target_name": "Notion",
        "prompt_text": "Top 3 workspace tools for startups?",
        "response_text": "1. Coda -- great for structured databases.\n2. Notion -- flexible and easy to start with.\n3. Confluence -- best for large enterprise docs.",
        "expected": {"sentiment": "positive", "target_mentioned": True, "recommended": True, "rank_position": 2},
    },
    {
        "name": "ranked_list_target_first",
        "target_name": "Notion",
        "prompt_text": "Which workspace app should I pick first?",
        "response_text": "1. Notion is the most versatile starting point.\n2. Obsidian if you want local-first notes.\n3. Evernote for simple note-taking.",
        "expected": {"sentiment": "positive", "target_mentioned": True, "recommended": True, "rank_position": 1},
    },
    {
        "name": "discovered_unknown_company",
        "target_name": "Notion",
        "prompt_text": "What are some newer note-taking apps worth trying?",
        "response_text": "Notion is solid, but also check out Anytype and Capacities -- both are newer local-first alternatives gaining traction.",
        "expected": {"sentiment": "positive", "target_mentioned": True, "recommended": True, "rank_position": None},
        "expected_mentioned_companies_include": ["Anytype", "Capacities"],
    },
    {
        "name": "mixed_sentiment_leans_negative",
        "target_name": "Notion",
        "prompt_text": "Any downsides to using Notion for documentation?",
        "response_text": (
            "Notion has a nice editor, but the search is slow and the API is limited, which makes it "
            "frustrating for anything beyond casual use."
        ),
        "expected": {"sentiment": "negative", "target_mentioned": True, "recommended": False, "rank_position": None},
    },
    {
        "name": "competitor_only_mentioned",
        "target_name": "Notion",
        "prompt_text": "What's the best tool for engineering wikis?",
        "response_text": "Confluence is the standard choice for engineering teams already on Atlassian tools.",
        "expected": {"sentiment": None, "target_mentioned": False, "recommended": False, "rank_position": None},
        "expected_mentioned_companies_include": ["Confluence"],
    },
    {
        "name": "brand_only_no_competitors_named",
        "target_name": "Notion",
        "prompt_text": "What can I use Notion for?",
        "response_text": "Notion works well for personal task lists, team wikis, and lightweight CRMs.",
        "expected": {"sentiment": "positive", "target_mentioned": True, "recommended": False, "rank_position": None},
    },
]
