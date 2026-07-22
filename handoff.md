# Session handoff

## Currently verified
- Whole-stack `docker compose up --build` works end to end: all 7 containers (postgres, redis, migrate, api, worker-pipeline, worker-interactive, frontend) came up clean, migrate exited 0, both workers started with no crash loop (sweeper cron fired successfully), `GET /health` returned `200` with DB+Redis both `ok`, frontend served `200`, and a real `POST /companies/resolve` round-tripped through CORS + API key + DB write.
- Backend test suite: `cd backend && pytest` → 256 passed, 1 skipped with no real keys present; 256 passed, 1 failed with real keys present (same pre-existing Groq JSON-mode bug, unrelated).
- `ruff check .` passes clean on `backend/`.
- Simplified key format (`GOOGLE_EXEC_KEYS=AIza...,AIza...`, no `id:secret:org`) authenticates correctly against real Google AI Studio and Groq.

## Changes this session
- Added a root-level `docker-compose.yml` that runs the whole app in one command: postgres, redis, a one-off `migrate` (alembic) step, `api`, `worker-pipeline`, `worker-interactive`, `frontend` — plus `backend/Dockerfile`, `frontend/Dockerfile`, and `.dockerignore` for each. `backend/docker-compose.yml` (postgres+redis only) kept as the native/hot-reload dev path.
- **Bug fix**: `.env.example`'s `CORS_ORIGINS` was `http://localhost:5173` (Vite's default) but this project's `vite.config.ts` runs the frontend on `8080` — would have broken every frontend→backend call with a CORS error even in the manual setup, not just Docker. Fixed in `.env.example` and the real `backend/.env`.
- Updated `README.md`'s Getting Started: leads with `docker compose up --build`, keeps the manual per-process steps as an explicit "native, for hot reload" alternative.
- Removed the stale duplicate `backend/.env.example` that reappeared after last session's consolidation (IDE/linter restored it with the old `id:secret:org` format) — confirmed only one `.env.example` exists now, at the repo root.
- Updated `CLAUDE.md`: Required startup and Commands now mention the one-liner Docker path; Topic docs no longer points at `render.yaml` (deleted — deployment deliberately set aside, not lost).

## Verification run
- Tore down the old `backend/docker-compose.yml` stack first to free ports 5432/6379, then `docker compose up --build -d` from repo root.
- `docker compose ps -a`: postgres/redis healthy, migrate `Exited (0)`, api/frontend/both workers `Up`.
- `curl localhost:8000/health` → `{"status":"ok","checks":{"database":"ok","redis":"ok"}}`; `curl localhost:8080/` → `200`.
- `docker compose logs worker-pipeline worker-interactive` → clean startup, sweeper cron ran once successfully.
- `POST /companies/resolve` with `Origin: http://localhost:8080` + real `X-API-Key` → `200` with a real company row created.
- Torn down with `docker compose down` after verification (no state left running).

## Still broken or unverified
- Nothing pushed yet — this session's changes (Docker files, README, CLAUDE.md, CORS fix) are local only.
- Known, not fixed (carried over): Groq's JSON mode requires the literal word "json" in the prompt messages; `backend/app/llm/prompts/evaluation.jinja` doesn't contain it, so Stage B evaluation 400s against real Groq traffic. Blocks Phase 21's real-provider smoke test.
- The Docker frontend image runs `npm run dev` (not a production build) — fine for local use, but if a "real" containerized frontend build is ever wanted, it still needs the earlier-identified fix to `vite.config.ts` (currently always targets Cloudflare Workers on `vite build`, which won't run in a plain Node container).

## Next best action
1. Review and commit this session's changes, push, confirm CI still green (unaffected by Docker additions, but worth checking).
2. Fix `backend/app/llm/prompts/evaluation.jinja`'s Groq JSON-mode issue before re-running Phase 21's real-provider e2e test.

## Files changed
- `docker-compose.yml` (new, repo root)
- `backend/Dockerfile`, `backend/.dockerignore` (new)
- `frontend/Dockerfile`, `frontend/.dockerignore` (new)
- `.env.example` (CORS_ORIGINS fix), `backend/.env` (CORS_ORIGINS fix, real file)
- `backend/.env.example` (removed again — stale duplicate)
- `README.md`, `CLAUDE.md`
