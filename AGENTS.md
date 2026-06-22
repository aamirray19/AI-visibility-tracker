# AGENTS.md

## Project Overview

AI Visibility Tracker is an authenticated analytics platform for measuring how visible a brand is in AI-generated answers.

Current stack:

- Frontend: Next.js App Router in `frontend/`
- Backend: FastAPI in `backend/app/`
- Database layer: SQLModel + Alembic migrations in `backend/app/models/` and `backend/alembic/`
- Queue/cache target architecture: Redis + ARQ
- Target production services: Vercel, Render, Supabase Postgres/Auth, Redis Cloud

Current runtime baseline:

- `GET /health` exists in the FastAPI app
- Phase 1 repository baseline is complete
- Phase 2 schema and migration baseline is complete
- Auth, campaign APIs, workers, and dashboards are not implemented yet

## Required Startup

1. Read `PROGRESS.md`
2. Read `feature_list.json`
3. Read `plan.md`
4. Read relevant docs under `docs/`
5. Understand the current phase boundary before writing code
6. Do not write feature code until baseline verification and current implementation status are understood

Minimum docs to read first:

- `docs/system-design.md`
- `docs/testing.md`
- `docs/decisions.md`

## Commands

Current commands:

- Backend install/setup: `cd backend && pip install -e ".[dev]"`
- Frontend install/setup: `cd frontend && npm install`
- Backend tests: `cd backend && pytest`
- Frontend unit tests: `cd frontend && npm test`
- Frontend lint: `cd frontend && npm run lint`
- Frontend build: `cd frontend && npm run build`
- Frontend E2E: `cd frontend && npx playwright test`
- Current smoke check: start the backend locally and call `GET /health`
- Docker baseline: `docker compose up --build`

## Hard Constraints

- Work on one feature or one planned phase at a time.
- Follow `plan.md` and complete the current phase before moving ahead.
- Do not mark a feature or phase as passing unless its verification command has been run successfully in the current session.
- Do not skip tests because the change looks small.
- Do not refactor unrelated code while implementing a feature.
- Do not revert unrelated worktree changes unless the user explicitly asks.
- Keep automated tests on local or mocked infrastructure only.
- Never point tests at production Supabase, Redis Cloud, or Gemini credentials.
- Record evidence in `feature_list.json` and `PROGRESS.md`.

## Definition Of Done

Done means:

1. Relevant unit or API tests pass
2. Migration or runtime checks pass when schema/runtime code changed
3. Smoke or E2E checks pass when user-facing behavior changed
4. Evidence is recorded in `PROGRESS.md`
5. Feature or phase status is updated in `feature_list.json`
6. `docs/decisions.md` is updated when an implementation decision changes or clarifies the design
7. `session-handoff.md` is updated when stopping mid-stream or handing work to the next session

## Topic Docs

- System design and product behavior: `docs/system-design.md`
- Testing standards: `docs/testing.md`
- Decision log: `docs/decisions.md`
- Implementation roadmap: `plan.md`
- Phase execution record: `PROGRESS.md`
- Feature tracking: `feature_list.json`

## Working Rules

- Start by understanding the latest completed phase and the next planned phase.
- Use TDD for new behavior: write the failing test first, verify it fails, then implement the minimum code to pass.
- Keep Alembic migrations as the database source of truth.
- Keep all campaign data behind FastAPI; do not design direct frontend table access.
- Treat `docs/system-design.md` as the source of truth unless `docs/decisions.md` explicitly supersedes part of it.
