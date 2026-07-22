# Session handoff

## Currently verified
- Backend test suite is healthy: `cd backend && pytest` → 256 passed, 1 skipped (the real-provider e2e test skips correctly when no real key-pool env vars are set).
- `ruff check .` passes clean on `backend/`.

## Changes this session
- Rewrote `CLAUDE.md` to match this repo instead of the generic template it had (real commands, real docs, added `handoff.md` to Required startup / Definition of done).
- Fixed `.github/workflows/ci.yml`: added `DATABASE_URL`, `REDIS_URL`, `API_KEY` to the `pytest` step's env block.

## Verification run
- Reproduced CI's exact failure locally: fresh docker-compose Postgres+Redis, `backend/.env` temporarily hidden, only the env vars `ci.yml` set at the time (`TEST_DATABASE_URL`/`TEST_REDIS_URL`) — `pytest` failed at collection with a `pydantic` `ValidationError` (`database_url`/`redis_url`/`api_key` required, none supplied).
- After adding `DATABASE_URL`/`REDIS_URL`/`API_KEY` to the `pytest` step, reran the same way → 256 passed, 1 skipped. `.env` restored immediately after.

## Still broken or unverified
- The `ci.yml` fix is verified locally only — not yet confirmed by an actual GitHub Actions run (nothing pushed).
- Found, not fixed: the real-provider e2e test's Stage B evaluation call (`llama-3.3-70b-versatile` on Groq) 400s — Groq's JSON mode requires the literal word "json" somewhere in the prompt messages, and `backend/app/llm/prompts/evaluation.jinja` doesn't contain it. Only surfaces when real keys are present (surfaced via local `.env` during this session's testing), so it didn't block the CI fix, but will block Phase 21's real-provider smoke test.

## Next best action
1. Review and commit `.github/workflows/ci.yml` + `CLAUDE.md`, push, confirm a real Actions run goes green.
2. Fix `backend/app/llm/prompts/evaluation.jinja` to include "json" so Groq's JSON mode stops 400ing, before re-running Phase 21's real-provider e2e test.

## Files changed
- `.github/workflows/ci.yml`
- `CLAUDE.md`
