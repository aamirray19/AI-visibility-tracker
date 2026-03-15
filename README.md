# AI Visibility Tracker

AI Visibility Tracker is a full-stack analytics platform for measuring how often a brand appears in AI-generated answers, how it ranks against competitors, and which URLs are cited as supporting sources.

It combines a Next.js frontend, a FastAPI backend, a Redis-backed ARQ worker, and PostgreSQL storage to run and analyze multi-model prompt campaigns.

## Project Overview

This project helps teams answer questions like:

- Is our brand being mentioned by AI assistants for commercial and informational queries?
- How visible are competitors in the same responses?
- Which domains are cited most often, and are they ours?
- How does performance differ by model/provider?

A campaign starts from a category (for example, `CRM software`), discovers candidate brands, generates prompt sets, executes them across configured models, and returns an analytics dashboard with aggregate and per-result metrics.

## Architecture Diagram

![System Architecture](docs/assets/visibility.png)

## Database Schema

![Database Schema](docs/assets/db_schema.png)

## Key Features And Capabilities

### Campaign setup and orchestration

- Brand discovery endpoint to generate category-specific candidate brands.
- Prompt generation with configurable campaign volume (`PROMPT_TARGET_COUNT`) and enforced commercial/informational mix.
- Campaign creation that persists prompts and enqueues one worker job per prompt.

### Asynchronous execution pipeline

- Redis + ARQ background processing to keep API latency low.
- Parallel provider execution via a shared abstraction (`GroqProvider`, `GemmaProvider`).
- Retry behavior and bounded worker concurrency for model calls and analysis tasks.

### Response analysis and scoring

- Structured extraction of target-brand mention, rank, sentiment, and mention context.
- Competitor extraction with rank and sentiment per mention.
- URL citation extraction and target-brand domain classification.

### Dashboard and analytics

- Aggregate metrics: AI visibility, citation share, share of voice, average rank, average sentiment.
- Per-model metrics for side-by-side provider comparison.
- Competitor leaderboard and top cited pages.
- Detailed prompt/result drill-down with pagination.
- Redis caching for completed dashboard responses (`DASHBOARD_CACHE_TTL_SECONDS`).

### API safeguards

- Optional bearer token guard for `/api/*` (`API_SECRET_KEY`).
- Route-level rate limits (`slowapi`) on discovery, campaign creation, and dashboard reads.

## High-Level System Architecture

The system is split into five runtime layers:

1. Frontend UI (`frontend/`): campaign setup and live dashboard polling.
2. API layer (`backend/app/main.py`, `api/campaigns.py`): request validation, auth, rate limits, orchestration.
3. Queue layer (`Redis` + `ARQ`): one job per prompt.
4. Worker pipeline (`backend/app/worker.py`): model execution + response analysis + persistence.
5. Data layer (`PostgreSQL` + `Redis`): normalized analytics storage and dashboard caching.

Mermaid architecture diagram code is intentionally not embedded here (provided separately).

## DB Schema

## Detailed Directory And Codebase Structure

```text
AI-visibility-tracker/
|-- docker-compose.yml                 # Orchestrates backend, worker, frontend, postgres, redis
|-- backend/
|   |-- Dockerfile
|   |-- requirements.txt
|   `-- app/
|       |-- main.py                    # FastAPI app, CORS, auth dependency, health routes
|       |-- worker.py                  # ARQ worker startup + process_prompt_job pipeline
|       |-- api/
|       |   `-- campaigns.py           # Campaign endpoints and dashboard aggregation logic
|       |-- core/
|       |   |-- config.py              # Pydantic settings + env loading
|       |   |-- db.py                  # Async SQLAlchemy/SQLModel engine + session factory
|       |   |-- limiter.py             # Global SlowAPI limiter
|       |   `-- queue.py               # Redis settings for ARQ
|       |-- models/
|       |   |-- campaign.py            # Campaign and Prompt tables
|       |   |-- result.py              # Raw model responses + analyzed target-brand fields
|       |   |-- cited_url.py           # Extracted cited URLs per result
|       |   `-- competitor_mention.py  # Competitor mentions per result
|       `-- services/
|           |-- llm.py                 # Brand discovery LLM call
|           |-- prompt_factory.py      # Prompt set generation
|           |-- executor.py            # Provider abstraction + parallel model execution
|           `-- analyzer.py            # Structured analysis extraction from responses
`-- frontend/
    |-- Dockerfile
    |-- package.json
    |-- next.config.ts
    |-- tsconfig.json
    |-- postcss.config.mjs
    |-- app/
    |   |-- layout.tsx                 # Global layout + metadata
    |   |-- page.tsx                   # Campaign setup flow (discover -> select -> create)
    |   `-- campaign/[id]/page.tsx     # Live analytics dashboard page
    |-- components/
    |   |-- setup/
    |   |   |-- CategoryInput.tsx      # Category input and discovery submit UI
    |   |   `-- BrandSelector.tsx      # Brand selection + campaign creation UI
    |   |-- dashboard/
    |   |   |-- MetricsGrid.tsx
    |   |   |-- ModelComparisonPanel.tsx
    |   |   |-- CompetitorLeaderboard.tsx
    |   |   `-- TopCitedPages.tsx
    |   `-- ui/
    |       `-- ErrorToast.tsx
    `-- lib/
        `-- utils.ts                   # `cn()` utility (clsx + tailwind-merge)
```

## Request/Processing Lifecycle

1. User enters a category in the frontend setup screen.
2. Frontend calls `POST /api/companies/discover`.
3. Backend uses `services/llm.py` to return 10-15 suggested brands.
4. User selects a brand and frontend calls `POST /api/campaigns/create`.
5. Backend generates prompts (`services/prompt_factory.py`), persists campaign/prompts, enqueues one ARQ job per prompt.
6. Worker (`process_prompt_job`) fetches model outputs in parallel using configured providers.
7. Worker stores raw responses, runs analyzer extraction, and writes structured entities (`Result`, `CitedUrl`, `CompetitorMention`).
8. Frontend dashboard polls `GET /api/campaigns/{id}` every 3 seconds until `is_complete=true`.
9. Backend computes aggregate metrics and caches completed dashboard payloads in Redis.

## Backend API Surface

- `POST /api/companies/discover`
- body: `{ "category": "CRM software" }`
- returns: `{ "brands": ["HubSpot", "Salesforce", ...] }`
- rate limit: `10/min`

- `POST /api/campaigns/create`
- body: `{ "brand": "HubSpot", "category": "CRM software" }`
- returns campaign id and prompt count
- rate limit: `5/min`

- `GET /api/campaigns/{campaign_id}?page=1&page_size=50`
- returns full dashboard payload (metrics, model comparison, competitors, cited pages, results)
- rate limit: `60/min`

- `GET /health`
- service health and version metadata

All `/api/*` routes are guarded by optional bearer auth:

- If `API_SECRET_KEY=""` (default), auth is disabled.
- If set, requests must include `Authorization: Bearer <API_SECRET_KEY>`.

## Setup And Run The Project

### Prerequisites

- Docker + Docker Compose plugin
- Groq API key
- Google AI Studio API key (used by Gemma provider)

### 1) Configure environment variables

Create a root `.env` file:

```bash
# Required
GROQ_API_KEY=your_groq_key
GOOGLE_AI_API_KEY=your_google_ai_key
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/ai_tracker

# Optional/with defaults
REDIS_URL=redis://redis:6379/0
API_SECRET_KEY=
FRONTEND_URL=http://localhost:3000
WORKER_MAX_JOBS=5
RATE_LIMIT_SLEEP_SECONDS=2.0
PROMPT_TARGET_COUNT=100
DASHBOARD_CACHE_TTL_SECONDS=3600
```

Notes:

- `DATABASE_URL` and `REDIS_URL` above match Docker service hostnames.
- `frontend` uses `NEXT_PUBLIC_API_URL=http://localhost:8000/api` in `docker-compose.yml`.

### 2) Start all services (recommended)

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend API docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

### 3) Verify health

```bash
curl http://localhost:8000/health
```

### 4) Watch worker execution

```bash
docker compose logs -f worker
```

## Operational Notes And Known Constraints

- No migration files (Alembic, etc.) are currently included in this repository.
- `backend/app/core/db.py` enforces `ssl="require"` for Postgres connections. If your local Postgres does not support SSL, adjust this for local development.
- Worker startup flushes the configured Redis DB (`flushdb`) before processing.
- Frontend dashboard polling stops once backend returns `is_complete=true`.

## Future Scope

- Provide exportable campaign reports (CSV/JSON/PDF) for stakeholder sharing.
- Expand provider adapters to include additional LLM backends and model routing policies.
- Add longitudinal tracking so campaigns can be compared over weekly/monthly snapshots.
- Build trend analytics for visibility deltas, rank movement, and sentiment drift.
- Add configurable prompt templates per industry/persona/use case.
- Support multi-tenant deployments with tenant isolation and usage metering.
- Introduce alerting workflows (email/Slack/webhooks) for major visibility changes.
- Add forecasting and anomaly detection for brand visibility performance.
