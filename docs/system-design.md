# System Design Document: AI Visibility Tracker

## 1. Overview

AI Visibility Tracker is an authenticated analytics platform for measuring how visible a brand is in AI-generated answers. A user signs in, creates campaigns for a product category and target brand, and views campaign history plus live dashboards showing brand mentions, rank, sentiment, cited sources, competitor mentions, and model/provider execution status.

The target system is a modernized version of the current prototype. It keeps the core split of Next.js frontend, FastAPI backend, PostgreSQL storage, Redis-backed background processing, and ARQ workers, but updates the production architecture around Supabase Auth, owner-scoped campaign data, Gemini grounded search as the default provider, Redis key isolation, Alembic migrations, automated verification, and managed deployment on Vercel, Render, Supabase, and Redis Cloud.

The design favors a fresh repository implementation. Current prototype details are treated as baseline context only; the target design below is the implementation source of truth.

## 2. Goals

- Provide email/password authentication through Supabase Auth.
- Ensure every campaign belongs to an authenticated user.
- Keep all campaign, prompt, result, citation, and competitor data behind FastAPI; the frontend must not directly query database tables.
- Let users create brand visibility campaigns from a category and selected brand.
- Generate a fixed prompt set of 50 prompts per campaign: 25 commercial and 25 informational.
- Execute prompts asynchronously through ARQ workers.
- Use Gemini 4 31B grounded search as the default production provider for brand discovery, prompt generation, answer generation, and structured analysis.
- Store grounded-search citation metadata, not only URLs parsed from response text.
- Provide user campaign history and a live dashboard for active and previous runs.
- Use Alembic migrations for schema ownership.
- Support reliable local development and testing through Docker Compose, mock providers, local Postgres, and local Redis.
- Support production deployment on Vercel, Render, Supabase Postgres/Auth, and Redis Cloud.

## 3. Non-Goals

- Organization/workspace support in v1.
- Billing or paid plan management in v1.
- Campaign delete/archive behavior in v1.
- Direct frontend reads from Supabase database tables.
- WebSocket or server-sent event updates in v1; dashboard updates use polling.
- Human-in-the-loop review/editing of analysis results.
- Full report export workflows such as CSV/PDF/email reports.
- Longitudinal scheduled recurring campaigns, unless added after v1.
- Supporting every model provider up front; optional future adapters can add OpenAI, Perplexity, or other providers.

## 4. Requirements

### Functional Requirements

- Users can sign up, sign in, sign out, and restore sessions through Supabase Auth.
- The frontend sends Supabase JWTs to FastAPI for protected API calls.
- FastAPI verifies Supabase JWTs and derives the authenticated user id from token claims.
- Users can request brand discovery for a category.
- Users can select a brand and create a campaign.
- Campaign creation generates prompts and enqueues one background job per prompt.
- The campaign size is fixed at 50 prompts for the MVP.
- Each campaign has exactly 25 informational and 25 commercial prompts.
- Workers process prompts through environment-selected providers.
- Production provider defaults to Gemini 4 31B grounded search.
- Tests use mock providers and must never call production providers.
- Raw AI response text is stored for each result.
- Citation metadata from grounded provider responses is normalized and stored.
- Structured analysis extracts target-brand mention, rank, sentiment, mention context, and competitors.
- Users can list their own campaigns through `GET /api/campaigns`.
- Users can read only their own campaign dashboards through `GET /api/campaigns/{id}`.
- Dashboard responses include aggregate metrics, per-model/provider metrics, competitors, top cited pages, mentioned prompts, paginated results, and campaign status.
- Compact completed-dashboard summaries are cached with user-scoped Redis keys.
- Active campaign dashboards are polled by the frontend until complete, with room for slower polling/backoff.

### Non-Functional Requirements

- All protected `/api/*` routes must require a valid Supabase JWT outside explicitly configured test/dev bypasses.
- User ownership must be enforced in every campaign read/write path.
- Campaign creation must fail safely if queueing fails.
- Worker processing must preserve raw responses even if analysis fails.
- Redis keys must be environment- and purpose-prefixed.
- Worker startup must not flush Redis.
- Database schema must be managed by Alembic migrations.
- Automated verification must include frontend lint/build, backend tests, migration tests, and mocked smoke tests.
- Production configuration must be separated from local/test configuration.
- Automated tests must not hit production Supabase, Redis Cloud, or LLM providers.
- The frontend should be an operational app shell with compact dashboards, campaign history, clear failure states, and restrained visual styling.

## 5. Assumptions and Constraints

- V1 supports individual user ownership only, not organizations.
- Supabase Auth is the identity provider for production.
- Supabase Postgres is the production database.
- Local development and tests use local Docker Postgres and Redis.
- Redis Cloud is used in production for ARQ queue and lightweight dashboard summary cache keys.
- Production has one Redis Cloud instance with a small memory limit, so isolation is done with key prefixes only.
- Full raw AI response text is retained indefinitely in v1.
- Campaign delete/archive is deferred.
- Provider/model selection is environment-driven.
- Gemini 4 31B is the default production model for all LLM-backed runtime paths.
- Exact Gemini API model identifiers are configured through environment variables and must not be hardcoded.
- The backend uses four separate Gemini API keys: one each for brand discovery, prompt generation, grounded answer generation, and structured analysis.
- Mock providers are mandatory for automated tests.
- All campaign data access goes through FastAPI.
- The fresh repository should include `PROGRESS.md`, `feature_list.json`, `docs/decisions.md`, `.env.example`, and repeatable verification commands from the start.

## 6. High-Level Architecture

```text
Browser / Next.js App
  - Supabase Auth client
  - Authenticated app shell
  - Campaign history
  - Live dashboard polling
        |
        | HTTPS + Supabase JWT
        v
FastAPI API on Render
  - JWT verification
  - Owner-scoped campaign API
  - Dashboard aggregation
  - Cache reads/writes
        |
        | SQLAlchemy/SQLModel async sessions
        v
Supabase Postgres
        ^
        |
ARQ Worker on Render <---- Redis Cloud
  - Prompt jobs             - queue keys
  - Provider execution      - dashboard cache
  - Citation normalization  - prefixed cache keys
  - Structured analysis
        |
        | Provider SDK/API
        v
Gemini Grounded Search / Mock Providers
```

Runtime services:

- `frontend`: Next.js application deployed to Vercel.
- `api`: FastAPI service deployed to Render.
- `worker`: separate ARQ worker service deployed to Render.
- `postgres`: Supabase Postgres in production; local Postgres in Docker Compose.
- `redis`: Redis Cloud in production; local Redis in Docker Compose.
- `auth`: Supabase Auth in production; mocked auth/JWT verification in tests.
- `provider`: Gemini 4 31B grounded search in production; mock provider in tests.

## 7. API Design

All `/api/*` endpoints are protected by Supabase JWT auth unless explicitly marked public. The backend derives `user_id` from the verified token and applies ownership filtering.

### `GET /health`

Purpose: Health check for deployment checks and local smoke tests.

Response:

```json
{
  "status": "ok",
  "timestamp": "2026-06-21T00:00:00Z",
  "version": "1.0.0"
}
```

### `POST /api/companies/discover`

Purpose: Discover candidate brands for a category.

Request:

```json
{
  "category": "CRM software"
}
```

Response:

```json
{
  "brands": ["Salesforce", "HubSpot", "Zoho"]
}
```

Controls:

- Requires Supabase JWT.
- Uses environment-selected provider.
- Production provider: Gemini 4 31B using the discovery API key.
- Test provider: mock response fixture.
- No Redis-backed rate limiting is included in the MVP.

### `POST /api/campaigns`

Purpose: Create a campaign for the authenticated user.

Request:

```json
{
  "brand": "HubSpot",
  "category": "CRM software"
}
```

Response:

```json
{
  "id": 123,
  "brand": "HubSpot",
  "category": "CRM software",
  "status": "CREATED",
  "prompt_count": 50
}
```

Behavior:

- Creates campaign and prompts in one database transaction.
- Generates exactly 50 prompts: 25 commercial and 25 informational.
- Validates generated prompts for non-empty text, exact intent counts, and no duplicates after trimming/lowercasing.
- Retries prompt generation internally when provider output is malformed, incomplete, over-complete in a way that breaks the 25/25 split, or duplicate-heavy.
- Fails campaign creation without creating database rows if exactly 50 valid prompts cannot be produced after retries.
- Enqueues one ARQ job per prompt.
- Rolls back if queue enqueueing fails.
- Stores `owner_id` from JWT claims.

### `GET /api/campaigns`

Purpose: List campaign history for the authenticated user.

Query parameters:

- `page`: default `1`.
- `page_size`: default `25`, maximum `100`.
- Optional category/date filters can be added later. Status filtering should be derived from prompt states if needed.

Response:

```json
{
  "items": [
    {
      "id": 123,
      "brand": "HubSpot",
      "category": "CRM software",
      "status": "COMPLETED",
      "prompt_count": 50,
      "processed_count": 50,
      "created_at": "2026-06-21T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total": 1,
    "total_pages": 1
  }
}
```

### `GET /api/campaigns/{campaign_id}`

Purpose: Return owner-scoped dashboard data.

Query parameters:

- `page`: default `1`, minimum `1`.
- `page_size`: default `50`, maximum `200`.

Response shape:

```json
{
  "id": 123,
  "brand": "HubSpot",
  "category": "CRM software",
  "status": "PROCESSING",
  "total_prompts": 50,
  "processed_count": 12,
  "is_complete": false,
  "metrics": {},
  "per_model_metrics": [],
  "competitors": [],
  "top_cited_pages": [],
  "mentioned_prompts": [],
  "results": [],
  "pagination": {}
}
```

Controls:

- Returns `404` for missing campaigns or campaigns not owned by the authenticated user.
- Uses user-scoped cache keys for completed dashboards.
- Never returns another user's campaign data.

## 8. Data Model

The fresh implementation should use Alembic migrations as the source of schema truth. SQLModel/SQLAlchemy models must match migrations.

### `Campaign`

- `id`: primary key.
- `owner_id`: Supabase user id from JWT `sub`.
- `brand_name`: target brand.
- `category`: product category.
- `prompt_count`: planned prompt count, fixed at 50 for MVP.
- `created_at`: timezone-aware timestamp.
- `updated_at`: timezone-aware timestamp.

Indexes:

- `(owner_id, created_at desc)` for campaign history.
- `(owner_id, id)` for owner-scoped detail lookup.

Campaign status is not stored in the campaign row for the MVP. API responses derive status from associated prompt statuses:

- `FAILED`: all prompts are `FAILED`;
- `COMPLETED`: all prompts are `COMPLETED`;
- `PARTIAL`: all prompts are terminal, but the set contains a mix of `COMPLETED`, `FAILED`, or `PARTIAL`;
- `PROCESSING`: any prompt is `PROCESSING`, or there is a mix of `PENDING` plus any terminal prompt;
- `CREATED`: all prompts are `PENDING`.

### `Prompt`

- `id`: primary key.
- `campaign_id`: foreign key to `Campaign`.
- `text`: generated prompt text.
- `intent_type`: `commercial` or `informational`.
- `status`: `PENDING`, `PROCESSING`, `COMPLETED`, `PARTIAL`, or `FAILED`.
- `error_message`: nullable failure summary.
- `created_at`: timezone-aware timestamp.
- `updated_at`: timezone-aware timestamp.

Indexes:

- `(campaign_id, status)`.
- `(campaign_id, created_at)`.

### `Result`

- `id`: primary key.
- `prompt_id`: foreign key to `Prompt`.
- `provider`: provider key such as `gemini` or `mock`.
- `model`: model name/version used.
- `response_text`: raw model response text.
- `brand_mentioned`: boolean.
- `rank`: target-brand prominence rank.
- `sentiment_score`: float from `0.0` to `1.0`.
- `mention_context`: extracted snippet.
- `analysis_status`: `PENDING`, `COMPLETED`, or `FAILED`.
- `provider_metadata`: JSON for normalized provider response metadata.
- `created_at`: timezone-aware timestamp.

Indexes:

- `(prompt_id, provider)`.
- `(created_at)`.

### `CitedUrl`

- `id`: primary key.
- `result_id`: foreign key to `Result`.
- `url`: normalized URL.
- `domain`: normalized hostname/domain.
- `title`: nullable source title from provider metadata.
- `source_provider`: provider that supplied the citation.
- `is_target_brand`: whether the citation belongs to the target brand.
- `citation_type`: `grounding_metadata`, `text_extracted`, or future type.
- `metadata`: JSON for provider-specific citation details.
- `created_at`: timezone-aware timestamp.

Indexes:

- `(result_id)`.
- `(domain)`.
- `(is_target_brand)`.

### `CompetitorMention`

- `id`: primary key.
- `result_id`: foreign key to `Result`.
- `brand_name`: competitor brand.
- `rank`: competitor prominence rank.
- `sentiment_score`: competitor sentiment.
- `created_at`: timezone-aware timestamp.

Indexes:

- `(result_id)`.
- `(brand_name)`.

## 9. Detailed Component Design

### Frontend Application

- Built with Next.js and deployed on Vercel.
- Uses Supabase client for email/password authentication and session restoration.
- Stores no long-lived custom API secrets in the browser.
- Sends the Supabase access token as `Authorization: Bearer <jwt>` to FastAPI.
- Uses an authenticated app shell after login.
- Prioritizes campaign history as the first-class home view.
- Provides a campaign creation flow from category discovery to brand selection to campaign start.
- Provides a dashboard route for current and previous campaign runs.
- Uses compact metrics, dense tables, clear partial/failed states, and restrained animations.
- Polls active campaigns and stops polling when complete.

### Backend API

- Built with FastAPI and deployed as a Render web service.
- Verifies Supabase JWTs using configured Supabase JWKS/JWT settings.
- Provides dependency-injected current-user context.
- Applies owner filtering at the query layer.
- Owns all business logic for campaign creation, dashboard aggregation, and provider orchestration entrypoints.
- Exposes no direct database credentials to the frontend.

### Database and Migrations

- Uses Supabase Postgres in production and local Postgres in development/tests.
- Uses Alembic migrations owned by the backend.
- Migration tests run against local/test Postgres.
- Schema changes are reviewed and tracked in `docs/decisions.md`.

### Provider Layer

- Uses a provider interface that returns structured output, not just text.
- Required provider response shape:

```json
{
  "provider": "gemini",
  "model": "gemini-model-name",
  "text": "AI response text",
  "citations": [
    {
      "url": "https://example.com/article",
      "domain": "example.com",
      "title": "Example",
      "metadata": {}
    }
  ],
  "metadata": {}
}
```

- Production provider defaults to Gemini 4 31B grounded search.
- Discovery, prompt generation, grounded answer generation, and structured analysis each use their own configured Gemini API key.
- Tests use mock providers.
- Optional future providers can implement the same interface.

### Analysis Layer

- Uses hybrid analysis:
  - deterministic citation/domain normalization from provider metadata;
  - Gemini structured analysis for target brand mention, rank, sentiment, mention context, and competitors.
- Analysis returns validated structured data.
- Analysis failures do not delete raw responses.

### Worker Layer

- Deployed as a separate Render worker service.
- Runs ARQ jobs from Redis Cloud.
- Does not call `flushdb` on startup.
- Uses global concurrency limits and provider-specific retry/backoff.
- Saves raw provider responses before analysis.
- Marks prompts with clear status transitions. Campaign status is derived from prompt states.

### Redis Layer

- Used for ARQ queue and lightweight completed-dashboard summary cache keys.
- Keys are prefixed by environment and purpose.
- Example keys:
  - `ait:prod:user:{user_id}:dashboard:{campaign_id}:p{page}:ps{page_size}`
  - `ait:prod:arq:*`
- The MVP uses one 30 MB Redis Cloud instance, so queue/cache isolation is done with prefixes only.
- Cache only compact completed-dashboard summaries, not raw response text or full paginated result payloads.
- Recommended cache key: `ait:prod:user:{user_id}:dashboard-summary:{campaign_id}`.
- Recommended cache TTL: 10-30 minutes.
- Detailed result pages should be fetched from Postgres.

## 10. Key Flows

### Authentication

1. User signs in through the frontend Supabase Auth client.
2. Supabase returns a session and access token.
3. Frontend calls FastAPI with `Authorization: Bearer <jwt>`.
4. FastAPI verifies the token and extracts `user_id`.
5. All protected handlers receive current-user context.

### Brand Discovery

1. User enters a category in the authenticated app.
2. Frontend sends `POST /api/companies/discover`.
3. Backend verifies JWT.
4. Backend calls the configured discovery provider.
5. Backend validates and normalizes brand names.
6. Frontend displays candidate brands.

### Campaign Creation

1. User selects a brand.
2. Frontend sends `POST /api/campaigns`.
3. Backend verifies ownership context.
4. Backend generates exactly 50 valid prompts through the configured provider: 25 commercial and 25 informational.
5. Backend creates `Campaign` and `Prompt` rows under `owner_id`.
6. Backend enqueues one ARQ job per prompt.
7. Backend commits the transaction and returns campaign metadata.
8. Frontend navigates to the dashboard and starts polling.

### Prompt Processing

1. Worker receives a prompt job.
2. Worker loads prompt and campaign.
3. Worker marks prompt `PROCESSING`.
4. Worker calls Gemini 4 31B grounded search or the configured provider.
5. Worker stores raw response and provider metadata in `Result`.
6. Worker normalizes citations from provider metadata into `CitedUrl`.
7. Worker runs structured analysis for mention, rank, sentiment, and competitors.
8. Worker writes analysis fields and competitor mentions.
9. Worker marks prompt `COMPLETED`, `PARTIAL`, or `FAILED`.
10. Campaign progress/status is derived later from prompt states.

### Campaign History

1. User opens the authenticated app shell.
2. Frontend calls `GET /api/campaigns`.
3. Backend returns only campaigns where `owner_id` matches the authenticated user.
4. Frontend displays previous runs and active campaign states.

### Dashboard Read

1. Frontend polls `GET /api/campaigns/{id}`.
2. Backend verifies the campaign belongs to the authenticated user.
3. Backend attempts user-scoped Redis cache lookup for completed dashboard summary data only.
4. Backend computes metrics from prompts, latest results, citations, and competitors when summary cache is absent.
5. Backend paginates detailed results directly from Postgres.
6. Backend caches compact completed dashboard summaries using user-scoped keys.
7. Frontend slows/stops polling when `is_complete` is true.

## 11. Scalability and Performance

- Campaign processing is asynchronous, keeping API creation latency bounded.
- Prompt processing is horizontally scalable through separate worker instances, subject to Redis queue capacity and provider limits.
- `WORKER_MAX_JOBS` controls worker concurrency.
- Provider calls use retry/backoff and global concurrency limits.
- Campaign size is fixed at 50 prompts for MVP: 25 commercial and 25 informational.
- The MVP uses one provider, so all 50 prompts go to that provider. If multiple providers are added later, dashboard denominators should continue to use prompt count while per-provider metrics are shown separately.
- Dashboard result pagination limits payload size.
- Compact completed dashboard summaries are cached in Redis with owner-scoped keys.
- Campaign history uses indexed `(owner_id, created_at)` queries.
- Citation and competitor aggregation should use indexed tables and database-level grouping.

Performance risks and mitigations:

- Large campaigns can make dashboard aggregation expensive; mitigate with indexes, compact cached summaries, and optional pre-aggregated campaign metrics.
- Provider calls can dominate latency; mitigate through async workers, smaller default prompt count, retries, and provider-specific timeouts.
- Redis contention can grow because queue and cache keys share one small Redis Cloud instance; mitigate with strict prefixes, short cache TTLs, and conservative payload sizes.

## 12. Reliability and Failure Handling

- Campaign creation must roll back if prompt persistence or queue enqueueing fails.
- Prompt generation must produce exactly 50 valid prompts after internal retries or fail before creating campaign rows.
- Worker startup must never flush Redis.
- Provider calls use bounded retries and timeouts.
- Discovery API key failure returns a generic discovery error.
- Prompt-generation API key failure returns a generic campaign creation error before any campaign rows are created.
- Grounded-search API key failure retries internally, then marks affected prompts `FAILED` when retries are exhausted.
- Analysis API key failure keeps raw response/citation data and sets `analysis_status=FAILED`.
- Raw responses are committed before structured analysis.
- Analysis failures set `analysis_status=FAILED` while retaining raw response and provider metadata.
- Prompt status reflects partial and failed processing clearly.
- Campaign status is derived from prompt states and is not stored on the campaign row for the MVP.
- Dashboard cache failures are logged but do not fail dashboard reads.
- Failed prompts can be surfaced in the UI, but retries are internal only for the MVP. No user-facing retry action is provided.
- A future dead-letter workflow can be added for repeatedly failing jobs.

## 13. Security

- Supabase Auth is the production identity provider.
- FastAPI verifies Supabase JWTs for protected API routes.
- `owner_id` is derived server-side from verified token claims, never from request body.
- All campaign queries are owner-scoped.
- `GET /api/campaigns/{id}` returns `404` for unauthorized access to avoid leaking resource existence.
- Frontend never receives database credentials.
- Tests use mocked auth and providers, not production secrets.
- CORS is restricted to configured frontend origins.
- Secrets are stored in Vercel/Render/Supabase/Redis Cloud environment management, not in Git.
- Raw AI response text is treated as untrusted user-visible content.

Security gaps to avoid in implementation:

- Do not leave auth optional in production.
- Do not use Supabase anon keys to read campaign tables directly from the browser.
- Do not trust user-supplied `owner_id`.
- Do not use shared dashboard cache keys that omit `user_id`.
- Do not let tests or local scripts default to production Supabase, Redis Cloud, or Gemini credentials.

## 14. Observability

MVP observability is intentionally minimal:

- `/health` verifies API liveness.
- Backend and worker write basic application logs for errors, campaign creation, worker prompt progress, provider failures, and analysis failures.
- Vercel, Render, Supabase, and Redis Cloud platform logs are used for operational inspection.
- No custom metrics, tracing, dashboards, or alerting are included in the MVP.

## 15. Deployment and Operations

### Local Development

Use Docker Compose for:

- local Postgres;
- local Redis;
- FastAPI backend;
- ARQ worker;
- Next.js frontend.

Local/test providers must be mockable. Local tests use local Postgres/Redis and mocked auth/provider paths.

### Production

- Vercel: Next.js frontend.
- Render: FastAPI API service.
- Render: separate ARQ worker service.
- Supabase: Auth and Postgres.
- Redis Cloud: ARQ queue and lightweight dashboard summary cache keys.

### Environment Variables

Core backend:

- `APP_ENV`
- `DATABASE_URL`
- `REDIS_URL`
- `REDIS_KEY_PREFIX`
- `FRONTEND_URL`
- `WORKER_MAX_JOBS`
- `DASHBOARD_CACHE_TTL_SECONDS`

Auth:

- `SUPABASE_URL`
- `SUPABASE_JWKS_URL` or equivalent JWT verification configuration
- `SUPABASE_JWT_AUDIENCE`
- `SUPABASE_PROJECT_REF`

Provider:

- `PROVIDER_MODE`
- `GEMINI_DISCOVERY_API_KEY`
- `GEMINI_PROMPT_API_KEY`
- `GEMINI_GROUNDED_SEARCH_API_KEY`
- `GEMINI_ANALYSIS_API_KEY`
- `GEMINI_DISCOVERY_MODEL`
- `GEMINI_PROMPT_MODEL`
- `GEMINI_GROUNDED_SEARCH_MODEL`
- `GEMINI_ANALYSIS_MODEL`

For MVP, all Gemini model variables should use Gemini 4 31B. Separate API keys are still used per task.

Frontend:

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Testing:

- `AUTH_MODE=mock`
- `PROVIDER_MODE=mock`
- `TEST_DATABASE_URL`
- `TEST_REDIS_URL`

### Required Repository Files

- `.env.example`
- `docker-compose.yml`
- `PROGRESS.md`
- `feature_list.json`
- `docs/decisions.md`
- backend migration folder
- backend test folder
- frontend test setup
- smoke/e2e test scripts

## 16. Tradeoffs and Alternatives

- Supabase Auth instead of custom auth: reduces implementation time and security surface, but adds dependency on Supabase token semantics and environment setup.
- FastAPI-only data access instead of direct Supabase table reads: stronger ownership controls and consistent business logic, but less use of Supabase client-side data features.
- Gemini grounded search as default provider: aligns answer generation with citation metadata, but increases dependency on one provider.
- Four Gemini API keys by task: gives operational separation for discovery, prompt generation, grounded search, and analysis, but increases environment setup complexity.
- Mock provider requirement for tests: prevents accidental provider spend and brittle tests, but requires disciplined provider interface design.
- Polling instead of WebSockets: simpler and reliable for v1, but less efficient for many active campaigns.
- Redis prefixes instead of separate Redis services: required for the 30 MB single Redis Cloud instance, but provides weaker isolation than separate databases/services.
- Raw response retention: useful for audit/debugging, but increases storage and content-safety obligations.

## 17. Risks and Mitigations

- Risk: Auth and ownership are added inconsistently.
  Mitigation: centralize JWT verification and owner-scoped query helpers; test non-owner access.
- Risk: Provider migration from Groq-style text responses to Gemini grounded metadata is underestimated.
  Mitigation: define a structured provider interface first and implement mock provider before Gemini.
- Risk: Citation metadata differs across providers.
  Mitigation: normalize citations into stable fields and keep provider-specific details in JSON metadata.
- Risk: Redis queue/cache keys collide or exceed the 30 MB Redis Cloud limit.
  Mitigation: enforce environment/purpose prefixes, keep cached dashboard payloads compact, use TTLs, and avoid storing raw responses in Redis.
- Risk: Worker startup accidentally deletes production Redis data.
  Mitigation: never use `flushdb`; add deployment check for non-destructive worker startup.
- Risk: Tests hit production providers or infrastructure.
  Mitigation: make mock modes explicit and fail fast when test env points at production-looking URLs/keys.
- Risk: Dashboard aggregation becomes slow.
  Mitigation: add indexes, cache completed dashboards, and introduce pre-aggregated campaign metrics if needed.
- Risk: Fresh repo loses implementation decisions.
  Mitigation: record decisions in `docs/decisions.md` and progress evidence in `PROGRESS.md`.

## 18. Rollout Plan

1. Repository baseline:
   - create fresh repo structure;
   - add `.env.example`, Docker Compose, backend/frontend skeletons;
   - add `PROGRESS.md`, `feature_list.json`, and `docs/decisions.md`.
2. Schema and verification:
   - add Alembic;
   - create initial migrations;
   - add backend test harness;
   - add frontend lint/build scripts;
   - add mocked smoke path.
3. Auth and ownership:
   - add Supabase frontend auth;
   - add FastAPI JWT verification;
   - add owner-scoped campaigns;
   - add campaign history endpoint.
4. Provider interface:
   - define structured provider contracts;
   - add mock provider;
   - add Gemini discovery, prompt generation, grounded answer generation, and analysis adapters.
5. Worker and dashboard:
   - add ARQ jobs;
   - persist raw results, citations, and analysis;
   - build dashboard aggregation and user-scoped cache keys.
6. Redis policy:
   - add key prefixes;
   - verify no Redis flushing;
   - add cache leak tests.
7. Frontend app shell:
   - build authenticated campaign history;
   - build create campaign flow;
   - build compact dashboard and status states.
8. Deployment:
   - configure Vercel, Render, Supabase, and Redis Cloud;
   - map env vars;
   - run deployment checks.
9. Beta:
   - use fixed 50-prompt campaigns;
   - inspect platform logs for provider errors, queue health, campaign duration, and Redis memory.
10. Production readiness:
   - confirm minimal MVP logging and `/health`;
   - review security;
   - increase limits gradually.

## 19. Testing Strategy

### Backend

- `pytest` unit tests for:
  - Supabase JWT verification;
  - mocked auth mode;
  - owner-scoped query helpers;
  - Redis cache key construction;
  - provider routing;
  - citation normalization;
  - dashboard aggregation.
- API tests for:
  - brand discovery;
  - create campaign;
  - list campaigns;
  - campaign detail;
  - non-owner rejection;
  - fixed 50-prompt creation with 25 commercial and 25 informational prompts.
- Migration tests:
  - run Alembic migrations against local/test Postgres.
- Worker tests:
  - process prompt with mock provider;
  - raw response persists before analysis;
  - partial/failed states;
  - citation and competitor insertion.

### Frontend

- Vitest + React Testing Library for:
  - login state;
  - authenticated app shell;
  - campaign history;
  - create campaign flow;
  - dashboard status rendering;
  - error messages.
- `npm run lint`.
- `npm run build`.

### Smoke

- Mocked provider campaign smoke test:
  - authenticate test user;
  - create campaign;
  - enqueue/process prompts;
  - persist results;
  - read dashboard.

### E2E

- Playwright test:
  - login;
  - create campaign with mocked backend/provider path;
  - view campaign history;
  - open dashboard;
  - view previous run.

### Deployment Checks

- Backend `/health`.
- Worker connects to Redis Cloud without flushing DB.
- Frontend authenticates through Supabase.
- Frontend calls FastAPI with Supabase JWT.
- Owner-scoped dashboard cache does not leak across users.

## 20. Open Questions

No open questions remain for the MVP design.
