# AI Visibility Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an authenticated AI visibility analytics platform where users create 50-prompt brand campaigns, workers process prompts through mocked or Gemini grounded providers, and dashboards show owner-scoped campaign metrics.

**Architecture:** Next.js owns the browser app and Supabase Auth session handling. FastAPI owns all protected data access, campaign orchestration, dashboard aggregation, and JWT verification. ARQ workers process prompt jobs through Redis, persist raw model responses, citations, structured analysis, and competitor mentions into Postgres.

**Tech Stack:** Next.js, Supabase Auth, FastAPI, SQLAlchemy/SQLModel, Alembic, PostgreSQL, Redis, ARQ, Gemini grounded search, pytest, Vitest, Playwright, Docker Compose, Vercel, Render, Supabase, Redis Cloud.

---

## File Structure

- [x] Create `frontend/` for the Next.js app, Supabase client, auth screens, campaign history, campaign creation flow, dashboard route, frontend tests, and build scripts.
- [x] Create `backend/app/` for FastAPI routes, auth dependencies, settings, database sessions, models, schemas, provider interfaces, campaign services, dashboard services, Redis helpers, and worker jobs.
- [x] Create `backend/alembic/` for schema migrations owned by the backend.
- [x] Create `backend/tests/` for API, service, auth, migration, provider, worker, Redis-key, and dashboard aggregation tests.
- [x] Create `scripts/` for local smoke tests and deployment checks.
- [x] Create `.env.example` with local, test, and production environment variable names but no real secrets.
- [x] Create `docker-compose.yml` for local Postgres, Redis, FastAPI, ARQ worker, and Next.js.
- [x] Update `PROGRESS.md` after every completed phase with commands run and evidence.
- [x] Update `feature_list.json` as features move from planned to implemented.
- [x] Update `docs/decisions.md` whenever implementation choices clarify or change the system design.
- [ ] Keep `docs/system-design.md` as the source-of-truth requirements document unless a decision supersedes it.

---

## Mandatory Testing Policy

Every phase below has a mandatory testing gate. A phase is not complete until unit/API tests, smoke tests, and E2E tests for the deepest runnable workflow have been executed and recorded in `PROGRESS.md`.

- [ ] Use `docs/testing.md` as the source of truth for required test layers, commands, safety rules, and evidence format.
- [ ] Add or update unit/API tests in the same phase as the implementation they cover.
- [ ] Add or update smoke coverage as soon as a local runnable path exists.
- [ ] Add or update Playwright E2E coverage as soon as the relevant frontend route exists.
- [ ] Run `scripts/check_no_prod_test_env.ps1` before smoke and E2E tests once that script exists.
- [ ] Use only local Postgres, local Redis, mock auth, and mock providers for automated tests.
- [ ] Treat any test that reaches production Supabase, Redis Cloud, or Gemini as a release blocker.

---

## Phase 1: Repository Baseline

**Files:**
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/core/settings.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/package.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/src/app/page.tsx`
- Modify: `PROGRESS.md`
- Modify: `feature_list.json`
- Modify: `docs/decisions.md`

- [x] Add backend project metadata with FastAPI, uvicorn, SQLAlchemy/SQLModel, asyncpg, Alembic, pytest, httpx, redis, arq, pydantic-settings, and provider SDK dependencies.
- [x] Add frontend project metadata with Next.js, React, TypeScript, Supabase client, lint, build, Vitest, React Testing Library, and Playwright dependencies.
- [x] Add `GET /health` returning `status`, UTC `timestamp`, and app `version`.
- [x] Add settings that read all required environment variables from `docs/system-design.md`, with safe test/local defaults only for non-production modes.
- [x] Add `.env.example` sections for backend core, auth, provider, frontend, and testing variables.
- [x] Add Docker Compose services for `postgres`, `redis`, `api`, `worker`, and `frontend`.
- [x] Add initial backend health test.
- [x] Add initial frontend page and build script.
- [x] Run backend tests with `pytest`.
- [x] Run frontend lint and build.
- [x] Run the Phase 1 mandatory testing gate from `docs/testing.md`: backend health unit/API test, frontend baseline test/build, local `/health` smoke check, and baseline Playwright render check if the Playwright harness exists in this phase.
- [x] Record the baseline commands and results in `PROGRESS.md`.

---

## Phase 2: Database Schema And Migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial_campaign_schema.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/models/campaign.py`
- Create: `backend/app/models/prompt.py`
- Create: `backend/app/models/result.py`
- Create: `backend/app/models/cited_url.py`
- Create: `backend/app/models/competitor_mention.py`
- Create: `backend/tests/test_migrations.py`
- Create: `backend/tests/test_campaign_status.py`
- Modify: `docs/decisions.md`
- Modify: `PROGRESS.md`

- [x] Define `Campaign` with `owner_id`, `brand_name`, `category`, `prompt_count`, `created_at`, and `updated_at`.
- [x] Define `Prompt` with `campaign_id`, `text`, `intent_type`, `status`, `error_message`, `created_at`, and `updated_at`.
- [x] Define `Result` with `prompt_id`, `provider`, `model`, `response_text`, analysis fields, `analysis_status`, `provider_metadata`, and `created_at`.
- [x] Define `CitedUrl` with normalized URL, domain, title, provider, target-brand flag, citation type, metadata, and timestamp.
- [x] Define `CompetitorMention` with result link, brand name, rank, sentiment, and timestamp.
- [x] Add indexes required by the system design: owner history, owner detail lookup, prompt status, result provider, citation domain, target brand, and competitor brand.
- [x] Implement campaign status derivation from prompt states: `CREATED`, `PROCESSING`, `COMPLETED`, `PARTIAL`, and `FAILED`.
- [x] Add migration test that applies Alembic migrations against test Postgres.
- [x] Add unit tests for every campaign status derivation branch.
- [x] Run migration tests and status tests.
- [x] Run the Phase 2 mandatory testing gate from `docs/testing.md`: backend schema/status unit tests, Alembic migration test, local API health smoke check, and baseline Playwright render check.
- [x] Record schema decisions and verification evidence.

---

## Phase 3: Auth And Owner Scope

**Files:**
- Create: `backend/app/auth/supabase.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/auth/mock.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/tests/test_auth.py`
- Create: `backend/tests/test_owner_scope.py`
- Modify: `backend/app/core/settings.py`
- Modify: `backend/app/main.py`
- Modify: `PROGRESS.md`

- [ ] Implement Supabase JWT verification using configured Supabase JWKS/JWT settings.
- [ ] Implement `AUTH_MODE=mock` for tests with explicit fake user IDs.
- [ ] Fail fast in production if auth settings are missing or `AUTH_MODE=mock`.
- [ ] Add a `current_user` dependency that derives `user_id` from verified token claims.
- [ ] Protect all `/api/*` routes through `current_user`.
- [ ] Keep `GET /health` public.
- [ ] Add tests for missing token, malformed token, valid mock token, production mock-mode rejection, and user ID extraction.
- [ ] Add tests proving non-owner access returns `404` for campaign detail paths.
- [ ] Run auth and owner-scope tests.
- [ ] Run the Phase 3 mandatory testing gate from `docs/testing.md`: auth unit/API tests, owner-scope tests, protected-route smoke check with missing and mock tokens, and auth-shell E2E check once the route exists.
- [ ] Record verification evidence.

---

## Phase 4: Provider Interface And Mock Providers

**Files:**
- Create: `backend/app/providers/base.py`
- Create: `backend/app/providers/mock.py`
- Create: `backend/app/providers/gemini.py`
- Create: `backend/app/providers/factory.py`
- Create: `backend/app/providers/schemas.py`
- Create: `backend/app/services/citations.py`
- Create: `backend/tests/test_provider_factory.py`
- Create: `backend/tests/test_mock_provider.py`
- Create: `backend/tests/test_citation_normalization.py`
- Modify: `backend/app/core/settings.py`
- Modify: `PROGRESS.md`

- [ ] Define provider response objects containing `provider`, `model`, `text`, `citations`, and `metadata`.
- [ ] Define provider methods for brand discovery, prompt generation, grounded answer generation, and structured analysis.
- [ ] Implement mock provider fixtures for deterministic tests.
- [ ] Implement provider factory routing by `PROVIDER_MODE`.
- [ ] Fail fast in tests if provider mode points at Gemini or a production-looking key.
- [ ] Implement citation normalization from provider metadata into URL, domain, title, source provider, citation type, target-brand flag, and JSON metadata.
- [ ] Add Gemini adapter skeleton that reads separate API keys and model env vars for discovery, prompt generation, grounded answer generation, and analysis.
- [ ] Ensure Gemini model identifiers are configurable and not hardcoded.
- [ ] Add tests for mock discovery, exact prompt generation shape, mock grounded answer, mock analysis, provider routing, and citation normalization.
- [ ] Run provider and citation tests.
- [ ] Run the Phase 4 mandatory testing gate from `docs/testing.md`: provider unit tests, citation normalization tests, mock provider smoke check, and baseline/frontend E2E checks that remain runnable.
- [ ] Record provider interface decisions.

---

## Phase 5: Campaign Creation API

**Files:**
- Create: `backend/app/api/campaigns.py`
- Create: `backend/app/api/companies.py`
- Create: `backend/app/schemas/campaigns.py`
- Create: `backend/app/services/campaign_creation.py`
- Create: `backend/app/services/prompt_validation.py`
- Create: `backend/app/queue/enqueue.py`
- Create: `backend/tests/test_brand_discovery_api.py`
- Create: `backend/tests/test_campaign_creation_api.py`
- Create: `backend/tests/test_prompt_validation.py`
- Modify: `backend/app/main.py`
- Modify: `PROGRESS.md`

- [ ] Implement `POST /api/companies/discover` with auth, provider discovery, brand normalization, and generic provider-error responses.
- [ ] Implement prompt validation for exactly 50 prompts, exactly 25 commercial prompts, exactly 25 informational prompts, non-empty prompt text, and no duplicates after trimming/lowercasing.
- [ ] Implement internal prompt-generation retry for malformed, incomplete, over-complete, or duplicate-heavy provider output.
- [ ] Implement `POST /api/campaigns` to create campaign and prompts under the authenticated `owner_id`.
- [ ] Ensure campaign creation rolls back if valid prompts cannot be produced.
- [ ] Ensure campaign creation rolls back if ARQ enqueueing fails.
- [ ] Enqueue one ARQ job per prompt.
- [ ] Return campaign metadata with `id`, `brand`, `category`, `status`, and `prompt_count`.
- [ ] Add tests for successful discovery, discovery auth failure, successful campaign creation, 50-prompt validation, duplicate prompt rejection, malformed prompt retry, provider failure rollback, enqueue failure rollback, and owner assignment from JWT.
- [ ] Run campaign creation tests.
- [ ] Run the Phase 5 mandatory testing gate from `docs/testing.md`: campaign unit/API tests, mock discovery and mock campaign creation smoke checks, and campaign creation E2E check once the frontend route exists.
- [ ] Record verification evidence.

---

## Phase 6: Worker Processing

**Files:**
- Create: `backend/app/worker/settings.py`
- Create: `backend/app/worker/jobs.py`
- Create: `backend/app/worker/run.py`
- Create: `backend/app/services/prompt_processing.py`
- Create: `backend/app/services/analysis.py`
- Create: `backend/tests/test_worker_prompt_processing.py`
- Create: `backend/tests/test_analysis_failure.py`
- Create: `backend/tests/test_worker_startup.py`
- Modify: `docker-compose.yml`
- Modify: `PROGRESS.md`

- [ ] Configure ARQ worker with Redis URL, key prefix, and `WORKER_MAX_JOBS`.
- [ ] Ensure worker startup never calls `flushdb`.
- [ ] Implement prompt job loading prompt and campaign records.
- [ ] Mark prompt `PROCESSING` before provider execution.
- [ ] Call grounded answer provider and persist raw response text plus provider metadata in `Result`.
- [ ] Normalize and persist citations from provider metadata into `CitedUrl`.
- [ ] Run structured analysis for target brand mention, rank, sentiment, mention context, and competitors.
- [ ] Persist competitor mentions into `CompetitorMention`.
- [ ] Mark prompt `COMPLETED` when response, citation, and analysis persistence succeeds.
- [ ] Mark prompt `PARTIAL` when raw response and citations persist but analysis fails.
- [ ] Mark prompt `FAILED` when grounded answer generation fails after bounded retries.
- [ ] Add tests proving raw response persists before analysis and survives analysis failure.
- [ ] Add tests for completed, partial, and failed prompt states.
- [ ] Add test or static guard proving worker startup does not flush Redis.
- [ ] Run worker tests.
- [ ] Run the Phase 6 mandatory testing gate from `docs/testing.md`: worker unit tests, analysis-failure tests, no-Redis-flush guard, mocked queued prompt smoke check, and all currently runnable E2E checks.
- [ ] Record worker behavior evidence.

---

## Phase 7: Campaign History And Dashboard API

**Files:**
- Create: `backend/app/services/campaign_history.py`
- Create: `backend/app/services/dashboard.py`
- Create: `backend/app/services/cache_keys.py`
- Create: `backend/app/cache/redis.py`
- Create: `backend/tests/test_campaign_history_api.py`
- Create: `backend/tests/test_dashboard_api.py`
- Create: `backend/tests/test_dashboard_cache_keys.py`
- Create: `backend/tests/test_dashboard_aggregation.py`
- Modify: `backend/app/api/campaigns.py`
- Modify: `PROGRESS.md`

- [ ] Implement `GET /api/campaigns` with owner filtering, pagination defaults, page-size max `100`, prompt counts, processed counts, created timestamps, and derived status.
- [ ] Implement `GET /api/campaigns/{campaign_id}` with owner filtering and `404` for missing or non-owned campaigns.
- [ ] Implement dashboard pagination defaults with page `1`, page size `50`, and max `200`.
- [ ] Aggregate total prompts, processed count, completion flag, aggregate metrics, per-provider metrics, competitors, top cited pages, mentioned prompts, detailed results, and pagination.
- [ ] Build Redis cache keys with environment, purpose, user ID, and campaign ID.
- [ ] Cache compact completed-dashboard summaries only.
- [ ] Keep detailed paginated result payloads fetched from Postgres.
- [ ] Use cache TTL from `DASHBOARD_CACHE_TTL_SECONDS`.
- [ ] Treat cache failures as logged misses, not API failures.
- [ ] Add tests for owner-scoped campaign list, non-owner detail rejection, active campaign dashboard, completed dashboard cache write/read, cache key user isolation, pagination, top citations, competitors, and failed/partial prompt display.
- [ ] Run dashboard and history tests.
- [ ] Run the Phase 7 mandatory testing gate from `docs/testing.md`: dashboard/history API tests, cache-key tests, owner-isolation smoke check, and dashboard E2E check once the frontend route exists.
- [ ] Record verification evidence.

---

## Phase 8: Frontend Authentication And App Shell

**Files:**
- Create: `frontend/src/lib/supabase.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/app/app/layout.tsx`
- Create: `frontend/src/app/app/page.tsx`
- Create: `frontend/src/components/auth/AuthForm.tsx`
- Create: `frontend/src/components/layout/AppShell.tsx`
- Create: `frontend/src/components/campaigns/CampaignHistory.tsx`
- Create: `frontend/src/tests/auth.test.tsx`
- Create: `frontend/src/tests/campaign-history.test.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `PROGRESS.md`

- [ ] Configure Supabase browser client from `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- [ ] Implement email/password sign up, sign in, sign out, and session restoration.
- [ ] Implement API helper that attaches `Authorization: Bearer <jwt>` to FastAPI requests.
- [ ] Redirect unauthenticated users to login.
- [ ] Render authenticated app shell after login.
- [ ] Make campaign history the first-class home view.
- [ ] Show loading, empty, failed, partial, processing, and completed campaign states.
- [ ] Add frontend tests for login state, session restoration behavior, auth header attachment, campaign history rendering, and error states.
- [ ] Run `npm run lint`.
- [ ] Run `npm run build`.
- [ ] Run frontend unit tests.
- [ ] Run the Phase 8 mandatory testing gate from `docs/testing.md`: frontend auth unit tests, app-shell tests, backend auth regression tests, login/app-shell smoke check, and login/session E2E check.
- [ ] Record verification evidence.

---

## Phase 9: Frontend Campaign Creation Flow

**Files:**
- Create: `frontend/src/app/app/campaigns/new/page.tsx`
- Create: `frontend/src/components/campaigns/CategoryDiscoveryForm.tsx`
- Create: `frontend/src/components/campaigns/BrandSelection.tsx`
- Create: `frontend/src/components/campaigns/CreateCampaignButton.tsx`
- Create: `frontend/src/tests/create-campaign.test.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `PROGRESS.md`

- [ ] Build category input for brand discovery.
- [ ] Call `POST /api/companies/discover` with Supabase JWT.
- [ ] Render discovered brand options.
- [ ] Allow selected brand campaign creation through `POST /api/campaigns`.
- [ ] Navigate to campaign dashboard after successful creation.
- [ ] Show clear failure states for discovery failure, campaign creation failure, unauthenticated session, and validation errors.
- [ ] Keep the UI compact, operational, and restrained.
- [ ] Add tests for discovery flow, brand selection, campaign creation, navigation, and failure states.
- [ ] Run frontend unit tests, lint, and build.
- [ ] Run the Phase 9 mandatory testing gate from `docs/testing.md`: campaign creation component tests, campaign creation API regression tests, mocked campaign creation smoke test, and create-campaign E2E test.
- [ ] Record verification evidence.

---

## Phase 10: Frontend Dashboard

**Files:**
- Create: `frontend/src/app/app/campaigns/[campaignId]/page.tsx`
- Create: `frontend/src/components/dashboard/DashboardSummary.tsx`
- Create: `frontend/src/components/dashboard/ProviderMetrics.tsx`
- Create: `frontend/src/components/dashboard/CompetitorTable.tsx`
- Create: `frontend/src/components/dashboard/CitedPagesTable.tsx`
- Create: `frontend/src/components/dashboard/PromptResultsTable.tsx`
- Create: `frontend/src/components/dashboard/DashboardStatus.tsx`
- Create: `frontend/src/tests/dashboard.test.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `PROGRESS.md`

- [ ] Fetch `GET /api/campaigns/{campaign_id}` with Supabase JWT.
- [ ] Poll active campaigns until `is_complete` is true.
- [ ] Slow polling with backoff for long-running campaigns.
- [ ] Stop polling when campaign is complete.
- [ ] Render aggregate metrics, per-provider metrics, competitors, top cited pages, mentioned prompts, paginated detailed results, and status.
- [ ] Show raw AI text safely as untrusted user-visible content.
- [ ] Render partial and failed prompt states clearly.
- [ ] Add result pagination controls.
- [ ] Add tests for active polling, completed stop condition, status rendering, metrics rendering, result pagination, and API error states.
- [ ] Run frontend unit tests, lint, and build.
- [ ] Run the Phase 10 mandatory testing gate from `docs/testing.md`: dashboard component tests, dashboard API regression tests, completed-dashboard smoke test, and dashboard E2E test.
- [ ] Record verification evidence.

---

## Phase 11: Local Smoke And E2E

**Files:**
- Create: `scripts/smoke_mock_campaign.ps1`
- Create: `scripts/check_no_prod_test_env.ps1`
- Create: `frontend/e2e/campaign.spec.ts`
- Modify: `docs/testing.md`
- Modify: `docker-compose.yml`
- Modify: `PROGRESS.md`

- [ ] Add a script that refuses to run tests when database, Redis, Supabase, or provider settings look production-like.
- [ ] Add mocked smoke script that authenticates as a test user, creates a campaign, processes prompt jobs, reads campaign history, and reads dashboard data.
- [ ] Add Playwright E2E for login, campaign creation with mocked backend/provider path, campaign history, dashboard, and previous run navigation.
- [ ] Document exact local verification commands in `docs/testing.md`.
- [ ] Run Docker Compose local stack.
- [ ] Run backend tests.
- [ ] Run frontend tests.
- [ ] Run mocked smoke script.
- [ ] Run Playwright E2E.
- [ ] Run the Phase 11 mandatory testing gate from `docs/testing.md`: full backend unit/API suite, full frontend unit suite, local mocked smoke test, and full Playwright E2E suite.
- [ ] Record all evidence in `PROGRESS.md`.

---

## Phase 12: Redis Policy And Safety

**Files:**
- Create: `backend/tests/test_redis_policy.py`
- Modify: `backend/app/services/cache_keys.py`
- Modify: `backend/app/cache/redis.py`
- Modify: `backend/app/worker/run.py`
- Modify: `docs/decisions.md`
- Modify: `PROGRESS.md`

- [ ] Enforce `REDIS_KEY_PREFIX` includes environment and application purpose.
- [ ] Prefix ARQ queue keys and dashboard cache keys separately.
- [ ] Use user-scoped dashboard summary keys such as `ait:prod:user:{user_id}:dashboard-summary:{campaign_id}`.
- [ ] Keep cache payloads compact and exclude raw response text and full paginated result rows.
- [ ] Use a 10-30 minute dashboard cache TTL.
- [ ] Add tests proving cache keys include user ID and do not collide across users.
- [ ] Add tests proving detailed result pages are not cached.
- [ ] Add guard or test proving Redis is never flushed on worker startup.
- [ ] Run Redis policy tests.
- [ ] Run the Phase 12 mandatory testing gate from `docs/testing.md`: Redis policy unit tests, cache isolation smoke test, full mocked smoke test, and full Playwright E2E suite.
- [ ] Record decisions and verification evidence.

---

## Phase 13: Deployment Configuration

**Files:**
- Create: `render.yaml`
- Create: `vercel.json`
- Create: `docs/deployment.md`
- Create: `scripts/deployment_check.ps1`
- Modify: `.env.example`
- Modify: `PROGRESS.md`

- [ ] Configure Vercel frontend build and required public environment variables.
- [ ] Configure Render FastAPI web service.
- [ ] Configure Render ARQ worker service.
- [ ] Configure Supabase Auth and Postgres environment mappings.
- [ ] Configure Redis Cloud URL and key prefix.
- [ ] Configure CORS to allow only the deployed frontend origin.
- [ ] Document all production environment variables and where each is set.
- [ ] Add deployment check script for API `/health`, frontend auth configuration, API JWT call, Redis connection, and worker startup without DB flush.
- [ ] Run deployment checks in staging before production.
- [ ] Run the Phase 13 mandatory testing gate from `docs/testing.md`: full backend suite, full frontend suite, local mocked smoke test, full Playwright E2E suite, and staging deployment checks.
- [ ] Record deployment evidence.

---

## Phase 14: Production Readiness Review

**Files:**
- Modify: `docs/decisions.md`
- Modify: `docs/testing.md`
- Modify: `PROGRESS.md`
- Modify: `feature_list.json`

- [ ] Confirm all protected `/api/*` routes require a valid Supabase JWT outside explicit test/dev bypasses.
- [ ] Confirm every campaign read/write path derives `owner_id` from authenticated user context.
- [ ] Confirm frontend never reads campaign tables directly from Supabase.
- [ ] Confirm tests use mock providers and never call production Gemini.
- [ ] Confirm production Gemini uses four separate API keys by task.
- [ ] Confirm exact Gemini model IDs are environment variables.
- [ ] Confirm campaign creation fails safely if queueing fails.
- [ ] Confirm worker preserves raw responses when analysis fails.
- [ ] Confirm Redis keys are environment- and user-scoped.
- [ ] Confirm worker startup does not flush Redis.
- [ ] Confirm Alembic migrations are the schema source of truth.
- [ ] Confirm local Docker Compose setup can run the full mocked workflow.
- [ ] Confirm frontend lint/build, backend tests, migration tests, mocked smoke tests, and Playwright E2E pass.
- [ ] Confirm platform logs are sufficient for MVP operations.
- [ ] Confirm `feature_list.json` accurately marks implemented and deferred features.
- [ ] Confirm `PROGRESS.md` contains final verification commands and outputs.
- [ ] Run the Phase 14 mandatory testing gate from `docs/testing.md`: final release verification commands, smoke test, E2E suite, and manual owner-isolation checks.

---

## Final Verification Checklist

- [ ] `cd backend && pytest`
- [ ] `cd backend && alembic upgrade head` against local/test Postgres
- [ ] `cd frontend && npm run lint`
- [ ] `cd frontend && npm run build`
- [ ] `cd frontend && npm test`
- [ ] `docker compose up --build`
- [ ] `scripts/smoke_mock_campaign.ps1`
- [ ] `cd frontend && npx playwright test`
- [ ] `scripts/deployment_check.ps1` against staging
- [ ] Manual check: user A cannot read user B campaign history or dashboard
- [ ] Manual check: completed dashboard cache key includes environment, user ID, and campaign ID
- [ ] Manual check: no production secrets are committed
- [ ] Manual check: worker logs show no Redis flush operation

---

## Deferred After MVP

- [ ] Organization/workspace support.
- [ ] Billing and paid plan management.
- [ ] Campaign delete/archive.
- [ ] WebSocket or server-sent event dashboard updates.
- [ ] Human review and editing of analysis results.
- [ ] CSV, PDF, or email report exports.
- [ ] Scheduled recurring campaigns.
- [ ] User-facing failed prompt retry.
- [ ] Additional providers such as OpenAI, Perplexity, or provider comparison mode.
- [ ] Custom metrics, tracing, dashboards, and alerting.
