# AI Visibility Tracker — Implementation Plan

> **For agentic workers:** This is a phase/task-level roadmap, not a granular TDD plan. Before executing any phase, flesh it out into bite-sized TDD steps with **superpowers:writing-plans**, then run it with **superpowers:subagent-driven-development** or **superpowers:executing-plans**. Checkboxes below track phase/task completion at the roadmap level.

**Goal:** Build the AI Brand Monitoring Platform end-to-end — FastAPI/ARQ backend implementing PRD phases 1–9, and a TanStack Start frontend implementing the six pages in system_design.md §6.1 — from the current state (backend deleted, frontend scaffold cleaned) to a deployed, working product.

**Architecture:** Exactly as specified in `system_design.md` v1.6 (source of truth — do not re-derive or contradict it). FastAPI + ARQ worker (two queues: `arq:interactive`, `arq:pipeline`) + Supabase Postgres + Redis Cloud, React/TanStack Start frontend on Vercel talking only to the FastAPI REST API (`X-API-Key`, no direct Supabase access, no auth).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async) + asyncpg + Alembic, ARQ, Redis, pydantic-settings, structlog, rapidfuzz, tldextract, httpx, pytest + pytest-asyncio + httpx.AsyncClient — backend. React 19, TanStack Start/Router/Query, Tailwind v4, shadcn/radix, recharts — frontend (already scaffolded).

## Context

`PRD.md` and `system_design.md` are both finalized (v1.6) and were reviewed together for gaps before this plan — three resolved: company/website are locked (not editable) after Phase 1 onboarding, the company/website mismatch check is a **hard** reject (`422`, no override), and the 9 monitoring-scope categories only supply guidance text into the fixed 4-category prompt mix (they don't reshape it). Both docs already reflect these decisions.

The repo currently has: `PRD.md`, `system_design.md`, and a `frontend/` TanStack Start scaffold that was just stripped of its unused Supabase-client/auth code (system_design.md §14/§19 mandate REST+`X-API-Key` only, no direct Supabase access, no auth screens — ever, by deliberate v1.5 decision). `frontend/` has the shadcn/radix UI kit, Tailwind v4, TanStack Router+Query wired, and one placeholder landing route. `backend/` does not exist — it was deleted in a prior commit; confirmed intentional, rebuilding from scratch. Two small patterns are worth resurrecting verbatim from git history at commit `bf10a9e` since they already match the spec exactly: the `AppError`/`register_error_handlers` error-contract pattern (`app/core/errors.py`) and the `require_api_key` `hmac.compare_digest` guard (`app/deps.py`). No migrations, Docker, CI, or deployment config exist anywhere yet.

Intended outcome: a working local pipeline (mocked LLM providers) provable end-to-end by Phase 11, hardened by Phase 13, wired to a real frontend by Phase 20, and proven against real LLM providers + deployed by Phase 21.

## Global Constraints

- **Source of truth is `system_design.md` v1.6** — every task below implements a specific section of it; if an implementation detail is ambiguous, re-read that section before improvising.
- **No auto-commit.** Each phase ends with a testing checkpoint; once it's green, stop and let the user review and commit manually. Do not run `git commit` as part of phase execution unless explicitly asked.
- **No new dependencies beyond what's listed here or in system_design.md** without a specific reason tied to a task — the ORM/migration/test-runner choices below (SQLAlchemy 2.0 async + asyncpg + Alembic; pytest + pytest-asyncio + httpx.AsyncClient) are pinned once, here, and apply to every phase.
- **Mock the `LLMProvider` protocol for all tests through Phase 20.** Real Google/Groq API calls happen exactly once, in Phase 21 — this keeps every earlier phase free, fast, and deterministic (system_design.md §20.1).
- **`llm/prompts/*.jinja`, never Python string literals** — every prompt template lives in its own file per system_design.md §18.
- **Never log or store a provider secret** — only `key_id`/`org` are allowed into Redis, logs, or Postgres (system_design.md §10.1).
- **Frontend never talks to Supabase or any LLM provider directly** — REST + `X-API-Key` to the FastAPI backend only (system_design.md §14).

---

## Phase 0: Repo & Infra Bootstrap

**Goal:** A `backend/` package that imports and runs, plus local dev infra, with nothing pipeline-specific yet.

- [x] **Task 1** — `backend/requirements.txt` + `backend/requirements-dev.txt`: FastAPI, uvicorn, SQLAlchemy[asyncio], asyncpg, alembic, arq, redis, pydantic-settings, structlog, rapidfuzz, tldextract, httpx, pytest, pytest-asyncio, pytest-cov. Delivers an installable backend skeleton per §18's repository structure.
- [x] **Task 2** — `backend/app/main.py`: bare FastAPI app, `GET /health` returning `{"status": "ok"}` (DB/Redis ping added in Phase 13). Entry point for `uvicorn app.main:app` per §3.
- [x] **Task 3** — `backend/docker-compose.yml`: local Postgres 15 + Redis 7 for dev/tests, mirroring §3's managed services (no pooler needed locally).
- [x] **Task 4** — `.github/workflows/ci.yml`: lint (ruff + eslint) + backend pytest + frontend build, on push.
- [x] **Task 5** — `backend/tests/conftest.py`: pytest fixtures for an async DB session against the docker-compose Postgres and a redis client, reused by every later phase's tests.

**Testing checkpoint:** `uvicorn app.main:app` boots locally; `GET /health` → 200; `docker-compose up` gives reachable Postgres+Redis; CI runs green on an empty test suite.

---

## Phase 1: Config, Errors, DB Foundation & Full Schema Migration

**Goal:** Every table in §4 exists in Postgres; config, error handling, and API-key guard are in place.

- [x] **Task 1** — `backend/app/config.py`: resurrect verbatim from commit `bf10a9e` (`git show bf10a9e:backend/app/config.py`), then extend with every var in §17 (key-pool env vars, model names, pipeline/limit/cost settings). One flat `Settings` class.
- [x] **Task 2** — `backend/app/core/errors.py`: resurrect `AppError` + `register_error_handlers` verbatim from `bf10a9e`. Wire into `main.py`. Declare the 8 error codes from §6 as constants (`INVALID_WEBSITE`, `COMPANY_MISMATCH`, `ENRICHMENT_LOW_CONFIDENCE`, `INVALID_STATE_TRANSITION`, `PROVIDER_UNAVAILABLE`, `SCAN_FAILED`, `RATE_LIMITED`, `COST_CEILING_EXCEEDED`).
- [x] **Task 3** — `backend/app/deps.py`: resurrect `require_api_key` verbatim from `bf10a9e`; add `get_db()` (async session dependency) and `get_redis()`.
- [x] **Task 4** — `backend/app/core/lifecycle.py`: the valid-state-transition table from §5 as one shared lookup (`{from_status: {allowed_to_statuses}}`) plus a `transition(scan, to_status)` helper that raises `AppError('INVALID_STATE_TRANSITION', ..., 409)` on an illegal move. Every status-changing endpoint/job in later phases calls this instead of hand-rolling its own if/else — the state machine is defined once, matching the DRY concern §14 already applies to `user_id`.
- [x] **Task 5** — `backend/app/db/models.py`: SQLAlchemy models for all 9 tables in §4 (`companies`, `scans`, `company_profiles`, `scan_entities`, `prompts`, `ai_responses`, `evaluations`, `mentions`, `scan_metrics`, `job_runs`) — field-for-field, including JSONB columns, unique constraints (`(scan_id, dedupe_hash)`, `(prompt_id, provider)`, `evaluations.response_id` unique), and every index listed in §4.
- [x] **Task 6** — `backend/migrations/` (Alembic `alembic.ini` + `env.py` targeting `database_url`) with one migration `0001_initial_schema.py` creating every table in §4 verbatim, enabling the `pgcrypto` extension for `gen_random_uuid()` in the same migration.
- [x] **Task 7** — `backend/app/db/repositories/`: thin CRUD modules, one per table (`companies.py`, `scans.py`, `profiles.py`, `entities.py`, `prompts.py`, `responses.py`, `evaluations.py`, `mentions.py`, `metrics.py`, `job_runs.py`). Every scan-scoped query in later phases goes through these — per §14's closing note, that makes a future `user_id` a migration + one `where` clause, not a rewrite.

**Testing checkpoint:** `alembic upgrade head` creates all tables cleanly against the docker-compose Postgres; `alembic downgrade base` reverses cleanly; a repository round-trip test (insert → read back) passes for each table; `AppError` → `register_error_handlers` unit test confirms the exact JSON shape in §6; `require_api_key` unit test confirms `401` on bad/missing key; `lifecycle.transition()` unit test confirms both a legal and an illegal move from §5's diagram.

---

## Phase 2: LLM Provider Abstraction & Key Pools

**Goal:** The one interface every later phase calls, fully testable with zero real API keys.

- [ ] **Task 1** — `backend/app/llm/base.py`: `LLMResponse` (Pydantic), `LLMProvider` Protocol (`complete(prompt, system, schema, tools, timeout)`), and the decorator chain **cost tracking → key-pool router → retry → timeout → raw client** per §10.
- [ ] **Task 2** — `backend/app/core/keypool.py`: `Key(id, secret, org)`, `KeyPool.acquire(est_tokens)` per §10.1's pseudocode, parsing the comma-separated `id:secret:org` env format from §17.
- [ ] **Task 3** — `backend/app/core/ratelimit.py`: the sliding-window `try_acquire` from §9 (`ratelimit:{key_id}`, `tokens:{key_id}`), plus adaptive-mode header parsing (`x-ratelimit-remaining-*`) per §15.1, with `RATE_LIMIT_COLD_START_*` as the pre-header floor.
- [ ] **Task 4** — `backend/app/core/circuit.py`: per-key breaker (`circuit:{key_id}`, 5 failures/60s → 5 min open, half-open probe after) and pool breaker (`circuit:pool:{pool}`, opens only when every key is down) per §10.1/§13.3.
- [ ] **Task 5** — `backend/app/core/pricing.py`: `PRICING_USD_PER_1K` table + `estimate_cost_usd`, raising on an unknown model per §15.3 (never silently `$0`).
- [ ] **Task 6** — `backend/app/llm/google.py`, `backend/app/llm/groq.py`: `GoogleAIStudioProvider`, `GroqProvider` implementing the `LLMProvider` Protocol, including Groq's tool-use loop for `web_search` → `citations` per §7.8.
- [ ] **Task 7** — `backend/app/llm/schemas.py`: shared home for the Pydantic structured-output models built out incrementally in Phases 4/5/7/9.
- [ ] **Task 8** — `backend/app/llm/prompts/.gitkeep`: empty dir now, real `.jinja` templates land per-phase starting Phase 4.

**Dependency note:** Needs Phase 1's `config.py` (key env vars) and `errors.py` (`AppError` on `PoolExhausted`/permanent key failures). Real provider adapters are wired but not exercised against live APIs until Phase 21 — every consumer phase mocks the `LLMProvider` Protocol.

**Testing checkpoint:** Per §20.1's "Key-pool router" row — 429 → cooldown + fallthrough to next key; breaker opens after 5 consecutive failures; pool breaker opens only when every key is down; round-robin vs. failover candidate ordering differs correctly; `PoolExhausted` raised only after `MAX_POOL_SPINS`. Cost table raises on an unknown model. No network calls — fake keys, docker-compose Redis, no real Google/Groq traffic.

---

## Phase 3: Onboarding & Scan Reuse (PRD Phase 1, §7.1)

**Goal:** `POST /companies/resolve` and `POST /scans` work end-to-end with no LLM involved — a scan row can be created and reused.

- [ ] **Task 1** — `backend/app/services/onboarding.py`: website format validation + SSRF guard (reject IPs/localhost/private ranges, non-http(s) schemes, 5s timeout, 1MB cap, max 2 redirects with host re-validation on each per §14), domain normalization (`tldextract`), name normalization (strip legal suffixes `inc|ltd|llc|corp|gmbh|pvt|pte`), homepage fetch + extraction (title/og/meta + body text, cached under `cache:enrich:{domain}`), **hard** mismatch check (`rapidfuzz.token_set_ratio < 60` **and** domain doesn't contain the name token → `422 COMPANY_MISMATCH`, no override — per the resolved gap), company upsert on `domain`.
- [ ] **Task 2** — `backend/app/services/onboarding.py` (cont.): scan-reuse logic per §7.1's pseudocode — active-scan check, `scan:recent:{domain}` Redis lookup, `?force=true` bypass. The `SETEX scan:recent:{domain}` write-on-completion call is stubbed here (real call added in Phase 10 once a scan can actually finish).
- [ ] **Task 3** — `backend/app/api/v1/companies.py`: `POST /companies/resolve` → `{company_id, name, domain, recent_scan_id?}`.
- [ ] **Task 4** — `backend/app/api/v1/scans.py`: `GET /scans` (cursor paginated), `GET /scans/{id}`, `DELETE /scans/{id}` (sets `scan:{id}:cancelled`). `POST /scans` (`202`) is built here **without** the job-enqueue call — the route validates, creates/reuses the scan row, and returns; the one-line `enqueue_job("enrich_company", ...)` is added as the last step of Phase 4, once that job exists.
- [ ] **Task 5** — `backend/app/main.py`: mount `companies.py` + `scans.py` under `/api/v1`, `require_api_key` on everything but `/health`, CORS allowlist from `cors_origins`.

**Dependency note:** Needs Phase 1 (schema, errors, deps, lifecycle) and Phase 2 only for `AppError` codes — no LLM calls yet.

**Testing checkpoint:** SSRF guard rejects `http://169.254.169.254`, `http://localhost`, non-http schemes; mismatch check returns `422 COMPANY_MISMATCH` on a deliberately wrong domain/name pair with no override path; duplicate `POST /scans` for an active scan returns the same scan, no new row; `scan:recent:{domain}` reuse returns `{reused: true}` without creating a new scan; `?force=true` bypasses reuse.

---

## Phase 4: Company Intelligence / Enrichment (PRD Phase 2, §7.2) + ARQ Bootstrap

**Goal:** First real pipeline job — `enrich_company` runs against a mocked `LLMProvider` and writes `company_profiles` v1.

- [ ] **Task 1** — `backend/app/worker/settings.py`: `PipelineSettings` (queue `arq:pipeline`, `max_jobs=20`, 120s timeout) and `InteractiveSettings` (queue `arq:interactive`, `max_jobs=5`, 60s timeout) per §8. Only `enrich_company` registered on `InteractiveSettings` for now.
- [ ] **Task 2** — `backend/app/services/enrichment.py`: builds the `gemini-2.5-flash` call (structured output, `temperature=0.2`) from name/domain/cached homepage text; handles §7.2's edge-case table (`is_known`/`confidence` → `warnings=['low_confidence']`, no competitors → `warnings=['no_competitors']`, **never blocks**); reads/writes `cache:enrich:{domain}` (7d TTL, gated on `confidence ≥ 0.7`).
- [ ] **Task 3** — `backend/app/llm/prompts/enrichment.jinja`: the enrichment prompt, delimits scraped homepage text as untrusted per §14's prompt-injection mitigation.
- [ ] **Task 4** — `backend/app/llm/schemas.py`: add the enrichment structured-output schema (industry, products, competitors, aliases, description, keywords, `is_known`, `confidence`).
- [ ] **Task 5** — `backend/app/worker/jobs.py`: `enrich_company(ctx, scan_id)` — loads scan/company, calls `enrichment.enrich(...)`, writes `company_profiles` v1, uses Phase 1's `lifecycle.transition()` to move `scans.status` `enriching → awaiting_verification` (or `failed`).
- [ ] **Task 6** — Wire the deferred `enqueue_job("enrich_company", scan_id, ...)` into `POST /scans` from Phase 3.
- [ ] **Task 7** — `backend/app/core/progress.py`: `publish(scan_id)` helper writing the `scan:{id}:progress` Redis hash (§9); `GET /scans/{id}` in `scans.py` reads it per §6's "Progress delivery". Every later job calls `progress.publish()`.

**Dependency note:** Needs Phase 2's `LLMProvider` Protocol (mocked in tests) and Phase 3's scan creation. First phase where ARQ actually runs a job — sets the `worker/jobs.py` + queue-registration pattern every later job reuses.

**Testing checkpoint:** Unit test calling `enrich_company(fake_ctx, scan_id)` directly with a mock `LLMProvider` returning canned JSON — asserts `company_profiles` v1 written, status transitions correctly, `warnings` set correctly for low-confidence/no-competitors cases. Cache test: second enrichment call for the same domain within 7d hits `cache:enrich:{domain}` and skips the LLM call.

---

## Phase 5: Verification (PRD Phase 3, §7.3) + Entity Freeze (§11 foundation)

**Goal:** The full human-gate loop — edit, confirm, AI-critic verify, accept — ending in a frozen `scan_entities` table.

- [ ] **Task 1** — `backend/app/api/v1/profiles.py`: `GET /scans/{id}/profile`, `PATCH /scans/{id}/profile` (writes `company_profiles` v2, `source='user_edited'` — industry/products/competitors/aliases/description only; **company and website are not accepted fields here**, per the resolved gap), `POST /scans/{id}/profile/confirm` (enqueues `verify_profile`).
- [ ] **Task 2** — `backend/app/services/verification.py`: `verify_profile` logic — sends the user's profile to `gemini-2.5-flash` as critic, parses `{verdict, issues}`; `issues_found` → back to `awaiting_verification` with `company_profiles.issues` populated; second confirm → writes v3 (`source='ai_verified'`).
- [ ] **Task 3** — `backend/app/llm/prompts/verification.jinja`: the critic prompt per §7.3.
- [ ] **Task 4** — `backend/app/services/entity_resolution.py`: normalization only for now (lowercase/NFKD-fold/strip-suffix/strip-punctuation per §11) plus the freeze step — on acceptance, flatten target + aliases + product names + competitors into `scan_entities` rows (`is_target` set correctly). Full match-order logic (fuzzy matching, word-boundary guard, discovered-name dedupe) is built in Phase 9, where it's first exercised against real response text.
- [ ] **Task 5** — `backend/app/worker/jobs.py`: add `verify_profile(ctx, scan_id)` to `InteractiveSettings`.

**Dependency note:** Needs Phase 4's `company_profiles` v1. `scan_entities` populated here is a hard prerequisite for Phase 9 (evaluation Stage A matches against it) — call this out during execution since it's easy to accidentally defer entity-table population.

**Testing checkpoint:** Integration test walking the full state machine: `awaiting_verification → (PATCH) → confirm → verifying → (issues_found) → awaiting_verification → (confirm again) → scope_pending`, asserting `company_profiles` v1/v2/v3 and `scan_entities` content match the accepted profile. Unit test for normalization rules. Mocked critic call — assert `verdict='issues_found'` prevents auto-transition past `awaiting_verification`.

---

## Phase 6: Monitoring Scope (PRD Phase 4, §7.4)

**Goal:** Validate and store the 9-category scope — trivial by design.

- [ ] **Task 1** — `backend/app/api/v1/scans.py`: `PUT /scans/{id}/scope` — validates against the fixed 9-category enum from PRD Phase 4, defaults to all 9, writes `scans.monitoring_categories`, `409 INVALID_STATE_TRANSITION` (via `lifecycle.transition()`) unless status is `scope_pending`.

**Dependency note:** Needs Phase 5's `scope_pending` state (reached only after entity freeze). No LLM, no new tables.

**Testing checkpoint:** Rejects an invalid category name; rejects the call outside `scope_pending`; confirms default-all-9 behavior when the request omits categories.

---

## Phase 7: Prompt Generation (PRD Phase 5, §7.5, §7.6 brand-only mix)

**Goal:** `generate_prompts` produces ~50 validated, deduped prompts and fans out execution jobs.

- [ ] **Task 1** — `backend/app/services/prompt_gen.py`: batched generation (~15/batch, ask 60/keep 50) against `gemini-2.5-flash` (`temperature=0.9`); fixed category mix 30/30/25/15 (`informational`/`commercial`/`competitor_discovery`/`product_specific`), reallocated per §7.6 only when `scans.brand_only=true` (`competitor_discovery` → `commercial`); scope categories injected as **guidance text only** — they do not change the mix percentages, per the resolved gap.
- [ ] **Task 2** — `backend/app/services/prompt_gen.py` (cont.): validation pipeline — sha256 `dedupe_hash` (relies on the DB unique constraint), near-dupe filter (`rapidfuzz.token_set_ratio > 90`), quality filter (< 5 words, "as an AI", literal `[company]` placeholder), one regeneration round for shortfall, proceed with ≥ 30 + warning if still short.
- [ ] **Task 3** — `backend/app/llm/prompts/prompt_generation.jinja`: the generation prompt, parameterized by scope text + brand-only flag.
- [ ] **Task 4** — `backend/app/worker/jobs.py`: `generate_prompts(ctx, scan_id)` on `arq:pipeline` — per §8's pseudocode, also does the fan-out: sets `scan:{id}:pending_exec`/`pending_eval` Redis counters, enqueues 100 `execute_prompt` jobs with deterministic `_job_id=f"exec:{prompt_id}:{provider}"`. `execute_prompt`'s body is a no-op stub until Phase 8 — this task only wires the enqueue calls.
- [ ] **Task 5** — `backend/app/api/v1/scans.py`: `POST /scans/{id}/launch` — `409` unless `scope_pending` (via `lifecycle.transition()`), enqueues `generate_prompts`.

**Dependency note:** Needs Phase 6's scope and Phase 5's frozen `scan_entities` (brand-only detection reads competitor count from there).

**Testing checkpoint:** Category mix percentages hold (±rounding) in both normal and brand-only modes; dedupe/near-dupe/quality filters each individually reject a crafted bad prompt; shortfall path proceeds with ≥30 + warning. `POST /launch` from `scope_pending` enqueues `generate_prompts`; running it against a mocked provider writes 30–50 `prompts` rows and sets `pending_exec`/`pending_eval` to `2 × prompt_count`. `execute_prompt` jobs asserted *enqueued* (by `_job_id`), not executed.

---

## Phase 8: AI Query Execution (PRD Phase 6, §7.7) + Citations (§7.8)

**Goal:** `execute_prompt` runs for real (mocked providers), `ai_responses` fills up, evaluation gets triggered (still a stub until Phase 9).

- [ ] **Task 1** — `backend/app/services/execution.py`: per §8's pseudocode — cancellation check (`scan:{id}:cancelled`), `pool.acquire()` from `google_exec`/`groq_exec`, provider adapter call (60s timeout), **upsert** `ai_responses` on `(prompt_id, provider)`, on success enqueue `evaluate_response` with `_job_id=f"eval:{resp.id}"` (stub call — body lands in Phase 9), `DECR pending_exec`/`pending_eval` via a shared `_decr` helper in `app/core/progress.py` (reused by Phase 9).
- [ ] **Task 2** — `backend/app/worker/jobs.py`: `execute_prompt(ctx, scan_id, prompt_id, provider)` on `arq:pipeline` — fills the Phase 7 stub.
- [ ] **Task 3** — `backend/app/llm/google.py` / `groq.py`: finalize execution call sites — `gemma-4-31b-it` (no tools) and `openai/gpt-oss-120b` (`tools=["web_search"]`), capturing `citations` from Groq's web-search loop into `ai_responses.citations`.
- [ ] **Task 4** — `backend/app/api/v1/sources.py`: `GET /scans/{id}/sources` — the citation-aggregation SQL from §7.8 (`jsonb_array_elements(citations)` grouped by domain, top 20).
- [ ] **Task 5** — Retry/failure policy per §13.1 wired into `execution.py`: 429 → cooldown + next-key (no ARQ retry consumed), 5xx/timeout → exponential backoff via Phase 2's router, pool breaker open → `status='skipped'` (§13.3's execution-side asymmetry — skip, don't defer).

**Dependency note:** Needs Phase 7's fan-out and Phase 2's key-pool router. `evaluate_response`'s body is still a no-op stub — Phase 9 tests must stub it explicitly so pending-counter math is verifiable without real evaluation logic.

**Testing checkpoint:** Idempotent upsert — running `execute_prompt` twice for the same `(prompt_id, provider)` produces one row; cancellation flag short-circuits before any provider call; pool-breaker-open path writes `status='skipped'` and still decrements counters. Mocked-provider integration test (one success, one simulated 429-then-success, one simulated total pool exhaustion) drives `pending_exec` to 0 across all 100 jobs. `GET /sources` returns correctly grouped/ranked citation domains against a fixture.

---

## Phase 9: Response Evaluation (PRD Phase 7, §7.9) + Full Entity Resolution (§11)

**Goal:** `evaluate_response` runs for real; Stage A + paired Stage B evaluators both work; `mentions` fills up; `aggregate_scan` gets triggered (stub until Phase 10).

- [ ] **Task 1** — `backend/app/services/entity_resolution.py`: complete the match-order algorithm from §11 — exact `name_norm` → exact alias → domain-in-text/citations → fuzzy (`rapidfuzz.token_set_ratio ≥ 88`) → unmatched (`entity_id=null`). Word-boundary matching (`\bnotion\b`), short-name (`≤3` chars) exact-only rule, discovered-name dedupe/fuzzy collapse pass over the `entity_id IS NULL` set.
- [ ] **Task 2** — `backend/app/services/evaluation.py`: Stage A — string-match `raw_response` against `scan_entities` via `entity_resolution.py` → `target_mentioned` + known-competitor mentions. Stage B — `llama-3.3-70b-versatile` via the `eval_a`/`eval_b` routing rule (`eval_a` if `provider == 'google_ai_studio'` else `eval_b`), structured JSON via Groq JSON mode + Pydantic validation + one repair re-prompt on parse failure, target-not-mentioned short-circuit (shorter prompt/output; call still happens for `mentioned_companies`).
- [ ] **Task 3** — `backend/app/llm/prompts/evaluation.jinja`: the evaluator prompt, explicitly scoping `sentiment` to the target company **as discussed in this response**, not overall tone, per §7.9.
- [ ] **Task 4** — `backend/app/worker/jobs.py`: `evaluate_response(ctx, response_id)` on `arq:pipeline` — writes `evaluations` (Stage A authoritative for `target_mentioned`/known-competitor mentions, Stage B authoritative for sentiment/rank/recommendation, neither overwrites the other), fans out `mentions`, `DECR pending_eval`, enqueues `aggregate_scan` at 0 with `_job_id=f"agg:{scan_id}"` (stub — Phase 10 fills in the body).
- [ ] **Task 5** — Failure policy per §13.3: pool breaker open on an eval call → **defer** (`_defer_by`, exponential up to `EVAL_MAX_DEFER_S=900`), distinct from execution's skip-on-breaker-open.

**Dependency note:** Needs Phase 8's `ai_responses` and Phase 5's frozen `scan_entities`. First phase where §11's full matching logic runs against real (mocked-LLM) response text.

**Testing checkpoint:** Per §20.1's "Entity resolution" row — match-order precedence fixture, word-boundary guard ("notion" vs "notionally"), short-name exact-only rule, discovered-name dedupe/fuzzy collapse. `target_mentioned=false` triggers the short Stage B path but the call still happens. Idempotency: `evaluations.response_id` unique — re-running produces one row. Malformed-JSON repair path: bad JSON once, good JSON second time → one repair re-prompt then success. Integration test drives `pending_eval` to 0 and asserts `aggregate_scan` enqueued exactly once.

---

## Phase 10: Aggregation (PRD Phase 8, §7.10, §12)

**Goal:** `aggregate_scan` produces a correct `scan_metrics` row with the early-fire guard in place; `finalize_scan` closes out the lifecycle.

- [ ] **Task 1** — `backend/app/services/aggregation.py`: every formula in §12 as pure SQL/SQLAlchemy over `mentions`/`evaluations`/`ai_responses` — AI Visibility, Recommendation Rate (+ when-mentioned variant), Share of Voice (denominator includes discovered companies), Overall Sentiment, Competitor Mention Frequency, Average Rank (+ `n`), Rank Distribution, Prompt Category Performance, Provider Comparison (+ per-provider `success_rate`), Top Sources. Assembles the exact JSON shape from §12 into `scan_metrics.metrics`.
- [ ] **Task 2** — `backend/app/worker/jobs.py`: `aggregate_scan(ctx, scan_id)` on `arq:pipeline` — the authoritative-SQL-over-counter guard from §8 (`db.scan_counts` check, re-defer if `evaluated < total` and deadline not passed), then computes + **upserts** `scan_metrics` (idempotent).
- [ ] **Task 3** — `backend/app/worker/jobs.py` (cont.): `finalize_scan(ctx, scan_id)` — applies §13.2's partial-results table (per-provider `≥0.95` → `completed`; one provider ≈0 → `completed_with_gaps`, excluded from metrics; `0.70–0.95` → `completed_with_gaps` + banner; `<0.70` or all unavailable → `failed`), sets `finished_at`, writes the deferred `SETEX scan:recent:{domain}` from Phase 3, clears the progress cache.
- [ ] **Task 4** — `backend/app/api/v1/scans.py`: `POST /scans/{id}/retry` — re-runs only failed/skipped `ai_responses`/`evaluations` rows, relying on the unique constraints for safety per §13.2.

**Dependency note:** Needs Phase 9's `mentions`/`evaluations`. The early-fire guard is the single most important correctness property in this phase — test it explicitly.

**Testing checkpoint:** Per §20.1's "Aggregation SQL" row — each metric formula against a fixed fixture, especially the R-denominator rule (only responses with an evaluation row count) and Share-of-Voice including discovered companies. Guard test: fire `aggregate_scan` with `pending_eval` at 0 but `evaluated < total` in Postgres — assert it re-defers instead of writing a partial `scan_metrics`. Idempotency: double-fire produces one upserted row. `finalize_scan` decision-table test: one fixture per row of §13.2's table, assert the resulting `scans.status`.

---

## Phase 11: Dashboard, Prompt Explorer & Remaining API Surface (PRD Phase 9, §7.11, §6)

**Goal:** Every read endpoint in §6 that depends on aggregation exists and is fast (no read-time computation).

- [ ] **Task 1** — `backend/app/api/v1/dashboard.py`: `GET /scans/{id}/dashboard` — one read of `scan_metrics.metrics`, no read-time aggregation.
- [ ] **Task 2** — `backend/app/api/v1/prompts.py`: `GET /scans/{id}/prompts` (paginated, filters `category`/`provider`/`sentiment`/`mentioned`), `GET /scans/{id}/prompts/{pid}` (both providers' responses + evaluations + citations joined).
- [ ] **Task 3** — `backend/app/main.py`: mount `profiles.py`, `dashboard.py`, `prompts.py`, `sources.py`; confirm every endpoint in §6's table now exists.
- [ ] **Task 4** — `backend/tests/fixtures/full_scan.py`: one reusable fixture seeding a complete scan (companies → scan → profile → entities → prompts → responses → evaluations → mentions → scan_metrics). Build once here; reused by this phase's tests and by Phase 21's end-to-end test.

**Dependency note:** Needs Phase 10's `scan_metrics` and Phase 9's `evaluations`/`mentions`. Intentionally thin — a read layer over data every prior phase already made correct.

**Testing checkpoint:** Using the Task 4 fixture: `GET /dashboard` returns the exact JSON shape from §12; `GET /prompts` paginates and filters correctly; `GET /prompts/{pid}` returns both providers' responses + evaluations + citations for one prompt.

---

## Phase 12: Reliability — Sweeper, Cancellation, Cost Fuse (§13)

**Goal:** The self-healing layer that makes the pipeline survive worker crashes/deploys.

- [ ] **Task 1** — `backend/app/worker/jobs.py`: `sweep_stalled_scans(ctx)` per §13.4 — queries scans stuck in `executing`/`evaluating`/`aggregating` for >10 min, `reconcile()`s each by recomputing truth from Postgres and re-enqueuing missing jobs via their deterministic `_job_id`s (no-op if already queued).
- [ ] **Task 2** — `backend/app/worker/settings.py`: register the sweeper as an ARQ cron on `InteractiveSettings` (every 2 min) per §8.
- [ ] **Task 3** — `backend/app/core/locks.py`: `lock:scan:{id}:advance` SETNX lock per §9, used anywhere two paths could double-advance the state machine (sweeper vs. a live job finishing concurrently).
- [ ] **Task 4** — Thread `scan:{id}:cancelled` checks (already in `execute_prompt`) through `evaluate_response` and `aggregate_scan` too, so `DELETE /scans/{id}` actually stops in-flight work between steps.
- [ ] **Task 5** — `backend/app/core/cost.py`: `cost:daily` Redis counter + `SCAN_COST_CEILING_USD` check invoked from Phase 2's cost-tracking decorator; aborts with `COST_CEILING_EXCEEDED` when either ceiling is hit.

**Dependency note:** Needs every job from Phases 4–10 to exist so `reconcile()` has real work to re-enqueue. Best done once the full happy-path pipeline (Phases 3–11) is proven, since testing "recovery" requires something to recover from.

**Testing checkpoint:** Per §20.1's "Sweeper" row — given a stalled-scan fixture (some `ai_responses` present, some missing), `reconcile` re-enqueues exactly the missing jobs and doesn't duplicate already-done work. Cost-fuse test: mock cumulative cost past `SCAN_COST_CEILING_USD` mid-scan, assert the next LLM call raises `COST_CEILING_EXCEEDED`. Cancellation test: set `scan:{id}:cancelled` mid-fan-out, assert no further job bodies run.

---

## Phase 13: Security Hardening, Observability & Config Finalization (§14, §16, §17)

**Goal:** Everything cross-cutting that doesn't have its own table/endpoint.

- [ ] **Task 1** — `backend/app/main.py`: CORS allowlist restricted to the exact Vercel domain (not `*`); confirm `X-API-Key` middleware covers every mounted router except `/health`.
- [ ] **Task 2** — `backend/app/main.py`: `GET /health` extended to ping Postgres + Redis per §3 (still no auth required).
- [ ] **Task 3** — `backend/app/core/logging.py`: `structlog` setup emitting `scan_id`, `job_name`, `provider`, `attempt` on every line; `scan_id` as the correlation ID from first HTTP request through last evaluation.
- [ ] **Task 4** — Sentry SDK wired into `main.py` (API) and `worker/settings.py` (worker).
- [ ] **Task 5** — `backend/migrations/000X_ops_view.py`: a plain Postgres view for §16's ops dashboard (scans by status, p50/p95 duration, per-provider success rate/p95 latency, cost per scan, breaker trips).
- [ ] **Task 6** — Checklist pass: confirm every `PRICING_USD_PER_1K` row (Phase 2) and every `MODEL_*` env var (§17) holds a real, currently-valid model string/rate — this is §10's flagged "verify model IDs before building the adapter" open item (`gemma-4-31b-it` in particular doesn't match any publicly documented model as of the spec's writing).
- [ ] **Task 7** — `backend/app/config.py`: final pass confirming every var in §17 is present with correct defaults (`ADAPTIVE_RATE_LIMIT=true`, `SCAN_SUCCESS_THRESHOLD=0.70`, `EVAL_MAX_DEFER_S=900`, etc.).

**Dependency note:** Purely cross-cutting — sequenced last-on-backend so it hardens a pipeline that already works end-to-end.

**Testing checkpoint:** `GET /health` reports degraded when Redis or Postgres is killed. Log lines from a full Phase-11-fixture pipeline run all carry `scan_id`; grep-test confirms no provider secret ever appears in a log line, Redis key, or DB row. CORS preflight from a non-allowlisted origin is rejected.

---

## Phase 14: Frontend Infra & API Client

**Goal:** A typed API client and query layer the six pages will all share.

- [ ] **Task 1** — `frontend/src/lib/api.ts`: thin fetch wrapper injecting `X-API-Key` (`VITE_API_KEY`) and base URL (`VITE_API_URL`) on every call, parsing `{error:{code,message,details}}` into a typed `ApiError`.
- [ ] **Task 2** — `frontend/src/lib/types.ts`: hand-written TypeScript types mirroring §4/§12's shapes (`Scan`, `CompanyProfile`, `ScanEntity`, `Prompt`, `DashboardMetrics`, etc.) — no codegen, no OpenAPI spec to generate from.
- [ ] **Task 3** — `frontend/src/hooks/`: one query/mutation hook per endpoint group (`useResolveCompany`, `useCreateScan`, `useScan`, `useProfile`, `useConfirmProfile`, `useScope`, `useLaunch`, `useDashboard`, `usePrompts`), all keyed on `scan_id` per §6.1. No global store — TanStack Query's cache is the store.
- [ ] **Task 4** — `frontend/src/router.tsx`: scaffold the `/scans/:id/...` route tree per §6.1 (individual route files added per-page in Phases 15–20).

**Dependency note:** Needs Phase 3's `POST /companies/resolve`/`POST /scans` and Phase 11's read endpoints live to test against.

**Testing checkpoint:** `useResolveCompany`/`useCreateScan` hooks exercised against the real local backend return typed data; a deliberately wrong `X-API-Key` produces a typed `ApiError` with `code='UNAUTHORIZED'`.

---

## Phase 15: Frontend — Onboarding Page

**Goal:** Replace the placeholder landing route with the real onboarding form.

- [ ] **Task 1** — `frontend/src/routes/index.tsx`: name+website form calling `POST /companies/resolve` then `POST /scans`. `COMPANY_MISMATCH` is a **hard** `422` (per the resolved gap) — surfaced as a blocking form error, not a "continue anyway" affordance.
- [ ] **Task 2** — same route: if `POST /scans` returns `{reused: true}` or an active/recent scan, redirect straight to that scan's current page based on its `status` (Phase 20 formalizes the full status→page map; this page only needs its own redirect case).

**Dependency note:** Needs Phase 14's client + Phase 3's backend live.

**Testing checkpoint:** Submit a valid company → lands on Verification once `awaiting_verification` is reached. Submit a mismatched name/website → inline blocking error, no scan created. Re-submit the same domain within `SCAN_REUSE_TTL_HOURS` → redirected to the existing scan.

---

## Phase 16: Frontend — Verification Page

**Goal:** The editable profile screen with the two-step confirm/critic loop.

- [ ] **Task 1** — `frontend/src/routes/scans.$id.verify.tsx`: editable sections for industry/products/competitors/aliases (add/edit/remove); company/website rendered **read-only**. `PATCH` on save, `POST /profile/confirm` on confirm.
- [ ] **Task 2** — same route: render verifier `issues` inline with keep/remove per flagged item after the first confirm returns `issues_found`, then a second confirm button to accept as-is.

**Dependency note:** Needs Phase 14 + Phase 5's backend live.

**Testing checkpoint:** Edit a competitor, confirm, see verifier issues rendered, remove a flagged one, confirm again → lands on Scope. Reload mid-flow with `scan_id` in the URL restores the correct page/state from `GET /scans/{id}`.

---

## Phase 17: Frontend — Scope Page

**Goal:** The smallest page in the app.

- [ ] **Task 1** — `frontend/src/routes/scans.$id.scope.tsx`: checkbox list of the 9 PRD monitoring categories, all checked by default, `PUT /scans/{id}/scope` on submit, navigate to Progress.

**Dependency note:** Needs Phase 6's backend endpoint.

**Testing checkpoint:** Uncheck a category, submit, confirm `monitoring_categories` matches the selection; submitting outside `scope_pending` surfaces the `409` cleanly.

---

## Phase 18: Frontend — Progress Page

**Goal:** Launch + poll, the one interval-based fetch in the app.

- [ ] **Task 1** — `frontend/src/routes/scans.$id.progress.tsx`: `POST /scans/{id}/launch` button, then a 2s `GET /scans/{id}` poll (TanStack Query `refetchInterval`) driving a progress bar off `progress.{stage, done, total}`; cancel button wired to `DELETE /scans/{id}`; auto-navigate to Dashboard on terminal status.

**Dependency note:** Needs Phases 7–10's backend pipeline actually running for the poll to show real progress — first frontend page that meaningfully exercises the full backend pipeline.

**Testing checkpoint:** Against a real local pipeline run (mocked providers, small `PROMPT_COUNT` for speed): launch, watch the bar move, cancel mid-run and confirm jobs actually stop, let one run to completion and confirm auto-navigation to Dashboard.

---

## Phase 19: Frontend — Dashboard Page

**Goal:** The payoff screen — one request, no client-side aggregation.

- [ ] **Task 1** — `frontend/src/routes/scans.$id.dashboard.tsx`: executive summary tiles, leaderboard, competitor comparison (or "Discovered competitors" when `brand_only`), sentiment breakdown, prompt category performance, provider comparison, top sources — all from the single `GET /scans/{id}/dashboard` payload. Use `recharts` (already installed), no new charting dependency.
- [ ] **Task 2** — same route: render the `completed_with_gaps` banner and single-vs-two-provider stamp (§13.2) when applicable.

**Dependency note:** Needs Phase 11's `GET /dashboard` and a completed scan to point at.

**Testing checkpoint:** Against Phase 11's fixture-seeded scan (fast path) and one real completed pipeline run: brand-only fixture renders "Discovered competitors"; `completed_with_gaps` fixture renders the banner and provider-set stamp.

---

## Phase 20: Frontend — Prompt Explorer Page

**Goal:** The per-prompt drill-down; finalize routing across all six pages.

- [ ] **Task 1** — `frontend/src/routes/scans.$id.prompts.tsx`: paginated list from `GET /scans/{id}/prompts` with `category`/`provider`/`sentiment`/`mentioned` filters; row expansion or detail route calling `GET /scans/{id}/prompts/{pid}` for prompt text, both providers' responses, evaluations, and mentioned companies.
- [ ] **Task 2** — `frontend/src/router.tsx`: finalize the `status → page` redirect map across all six routes so a reload at any lifecycle stage lands correctly.

**Dependency note:** Needs Phase 11's paginated endpoints.

**Testing checkpoint:** Filters narrow the list correctly; a row expands to show both providers' full responses + evaluation + citations; pagination doesn't refetch the whole set. Redirect-map smoke test: hit `/scans/:id/dashboard` for a scan still `executing`, confirm redirect to Progress instead of an error.

---

## Phase 21: End-to-End Integration, Real-Provider Smoke Test & Deployment

**Goal:** Prove the whole system against real LLM providers at least once, and ship deployment config.

- [ ] **Task 1** — `render.yaml`: `brandmon-api` (web service, `uvicorn app.main:app --port $PORT`, health check `/health`), `brandmon-worker-pipeline` (background worker, `arq app.worker.PipelineSettings`, **paid instance**), `brandmon-worker-interactive` (background worker, `arq app.worker.InteractiveSettings` + sweeper cron) — per §3.
- [ ] **Task 2** — Provision the real 11 keys/5 pools per §17 in Render env vars (not committed); confirm Supabase pooler connection string (transaction mode, port 6543) and same-region placement per §3.
- [ ] **Task 3** — Vercel project config for `frontend/`: `VITE_API_URL`/`VITE_API_KEY` pointed at the deployed Render API; backend CORS allowlist updated to the real Vercel domain.
- [ ] **Task 4** — `backend/tests/e2e/test_full_pipeline.py`: one real (not mocked) small-scale run — a real company through onboarding → enrichment → verification → scope → launch → execution → evaluation → aggregation → dashboard, against real Google/Groq APIs with `PROMPT_COUNT` turned down for cost, asserting the pipeline reaches `completed` or `completed_with_gaps` and the dashboard payload is well-formed. **First and only phase that spends real LLM tokens.**
- [ ] **Task 5** — `backend/tests/golden/`: the ~10–15 hand-labeled evaluator fixtures from §20.2 (clear positive/negative/neutral, unmentioned target, ranked list, unknown-company mention) — run manually whenever the eval prompt/model changes, not a CI gate.
- [ ] **Task 6** — One scripted manual QA walk of Onboarding → Verification → Scope → Progress → Dashboard → Prompt Explorer against the deployed stack. (Skipping a full Playwright E2E suite here — a browser-automation framework for a single-operator tool is more than this scale needs; revisit if the app grows beyond one user.)
- [ ] **Task 7** — Wire §16's alert thresholds (non-terminal scan >30 min, key permanently disabled, pool breaker open, pool 429 rate >20%/10min, queue depth >500, daily cost > threshold) into Sentry/Render's existing alerting — no new alerting service.

**Dependency note:** Needs every prior phase complete. Deliberately the only phase that talks to real LLM providers and touches deployment config — everything before it is provable on mocks and localhost.

**Testing checkpoint:** Full pipeline reaches a terminal status against real providers at least once; `job_runs` shows a clean trace; dashboard renders correctly for the real run; cost fuse and rate limiter behave sanely under real Groq/Google traffic (watch TPM per §15.1); deployed Vercel frontend talks to deployed Render backend end-to-end with no CORS/API-key issues.

---

## Critical Files

- `backend/app/db/models.py` — the whole schema in one place
- `backend/app/llm/base.py` — the provider abstraction every LLM call goes through
- `backend/app/core/lifecycle.py` — the single source of truth for legal scan-status transitions
- `backend/app/worker/jobs.py` — every ARQ job, the backbone of the pipeline
- `backend/app/services/evaluation.py` — Stage A/B evaluation logic
- `backend/app/services/aggregation.py` — every dashboard metric formula
- `frontend/src/lib/api.ts` — the only place the frontend talks to the backend

## Verification

This plan's own deliverable is `plan.md` at the repo root — verify it by re-reading it against `system_design.md` section-by-section (§1–§20) and confirming every section maps to at least one task above (it does, per the phase-to-section notes throughout).

Per-phase verification during execution: each phase's **Testing checkpoint** must pass (pytest for backend phases, manual QA against a running local stack for frontend phases) before moving to the next phase or considering that phase done. No phase auto-commits — stop after a green testing checkpoint and let the user review/commit manually, per the Global Constraints above.
