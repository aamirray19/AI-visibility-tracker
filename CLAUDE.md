# CLAUDE.md

## Project overview
AI Brand Monitoring Platform: submit a company + website, an LLM pipeline (Gemini for enrichment/verification/prompt-gen, Gemma + GPT-OSS for execution, Llama 3.3 for evaluation) generates ~50 prompts, queries them across two providers, evaluates the responses, and surfaces AI-visibility/sentiment/competitor metrics on a dashboard. Backend: FastAPI + ARQ worker (two queues) + SQLAlchemy async/asyncpg + Alembic, on Supabase Postgres + Redis. Frontend: React 19 / TanStack Start+Router+Query + Tailwind v4 + shadcn, calling the backend only via REST + `X-API-Key` (no Supabase/LLM access from the client, no auth — single-user by design).

## Required startup
1. Read `handoff.md` for context left by the previous session.
2. Read `plan.md` for current phase status (checkboxes = done/pending) and `system_design.md` for architecture — it is the source of truth; re-read the relevant section before improvising on any ambiguity.
3. Read `PRD.md` for product intent if the task touches user-facing behavior.
4. `.env.example` at the repo root has every var both apps need (backend + frontend) — copy it into `backend/.env` and `frontend/.env` and fill in real values if they don't already exist.
5. `docker compose up --build` from the repo root boots the whole stack (Postgres, Redis, migrations, API, both ARQ workers, frontend) in one command. For active backend/frontend iteration, run natively instead (see Commands) — no image rebuild per save.
6. Do not write feature code until you've checked `plan.md` for which phase/task this falls under and whether it's already marked done.

## Commands
- Whole stack, one command: `docker compose up --build` (repo root `docker-compose.yml`)
- Backend-only infra for native dev: `cd backend && docker-compose up -d` (Postgres + Redis only, no rebuild needed on save)
- Backend install/setup: `cd backend && pip install -r requirements-dev.txt && alembic upgrade head`
- Backend tests: `cd backend && pytest` (needs `TEST_DATABASE_URL`, `TEST_REDIS_URL` — see `tests/conftest.py`, defaults match `docker-compose.yml`)
- Backend lint: `cd backend && ruff check .`
- Backend dev server: `cd backend && uvicorn app.main:app --reload`
- Frontend install: `npm install --prefix frontend`
- Frontend lint: `npm run lint --prefix frontend`
- Frontend build: `npm run build --prefix frontend`
- Frontend dev server: `npm run dev --prefix frontend`
- Real-provider e2e (costs tokens, needs real keys): `cd backend && pytest tests/e2e/test_full_pipeline.py -v`
- Golden evaluator set (manual, not CI-gated): `cd backend && python tests/golden/run_golden.py`
- CI mirrors all of the above: `.github/workflows/ci.yml`

## Hard constraints
- `system_design.md` v1.6 is the source of truth for architecture — do not re-derive or contradict it.
- Work through `plan.md`'s phases in order; don't skip ahead or mark a phase done without its testing checkpoint passing.
- Mock the `LLMProvider` protocol for all tests except Phase 21's e2e/golden tests — real Google/Groq calls are opt-in and cost real tokens.
- Prompt templates live in `backend/app/llm/prompts/*.jinja`, never as Python string literals.
- Never log or persist a provider secret — only `key_id`/`org` are allowed into Redis, logs, or Postgres.
- Frontend never talks to Supabase or an LLM provider directly — REST + `X-API-Key` to the FastAPI backend only.
- No new dependencies beyond what's already in `requirements.txt`/`package.json` or specified in `system_design.md` without a concrete reason.
- No auto-commit — per user instruction, stop after a green testing checkpoint and let the user review/commit manually.
- Continuous phase execution: once mid-phase, keep going through `plan.md`'s tasks without stopping for permission between them.

## Definition of done
Done means:
1. Relevant `pytest` tests pass (backend) and/or the page is verified live against the local backend (frontend — no browser tool available, note this explicitly rather than claiming untested UI works)
2. `ruff check .` (backend) / `npm run lint` (frontend) pass
3. The phase's own "Testing checkpoint" in `plan.md` passes when a plan phase is being completed
4. No provider secret leaked into a log line, Redis key, or DB row (grep-check when touching key-pool/LLM code)
5. `plan.md`'s checkbox for the task is updated to reflect what was actually done
6. `handoff.md` is updated with anything the next session needs to know (blocked items, in-flight state, follow-ups)

## Topic docs
- Product requirements: `PRD.md`
- Architecture & design (source of truth): `system_design.md`
- Implementation roadmap & phase status: `plan.md`
- Local stack: root `docker-compose.yml` + `.env.example` (deployment config was deliberately set aside for now — `render.yaml` was removed, not lost; ask before assuming it should come back)
