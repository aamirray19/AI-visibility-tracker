# AI Visibility Tracker Testing Strategy

Testing is mandatory after every implementation phase in `plan.md`. A phase is not complete until its unit tests, smoke tests, and E2E tests have either passed or the phase has added the missing harness and documented why a narrower temporary command is the only runnable check at that point.

All automated tests must use local or mocked infrastructure. Tests must never call production Supabase, Redis Cloud, or Gemini providers.

## Required Test Layers

### Unit And API Tests

- Backend unit/API tests live in `backend/tests/`.
- Frontend unit/component tests live in `frontend/src/tests/`.
- Backend tests use `AUTH_MODE=mock`, `PROVIDER_MODE=mock`, `TEST_DATABASE_URL`, and `TEST_REDIS_URL`.
- Frontend tests mock Supabase sessions and FastAPI responses unless explicitly running against the local smoke stack.
- Every backend service, route, auth dependency, provider adapter, cache-key helper, worker job, and dashboard aggregation path must have focused unit or API tests.
- Every frontend auth, campaign history, campaign creation, dashboard, polling, loading, empty, partial, failed, and completed state must have component tests.

Required commands once harnesses exist:

```powershell
cd backend
pytest

cd ..\frontend
npm test
```

### Smoke Tests

- Smoke tests live in `scripts/` and run against the local Docker Compose stack.
- Smoke tests use mocked auth and mocked providers only.
- Smoke tests must cover the shortest full backend path available after each phase.
- Once campaign and worker functionality exists, the canonical smoke test is `scripts/smoke_mock_campaign.ps1`.

Minimum smoke coverage by maturity:

- Baseline: `/health` returns `200` from the local API.
- Auth: protected route rejects missing token and accepts mock token.
- Campaign creation: mock discovery and mock campaign creation succeed.
- Worker: queued mock prompt job is processed and persisted.
- Dashboard: campaign history and dashboard reads return owner-scoped data.
- Full MVP: login, create campaign, process prompts, read history, read dashboard.

Required commands once harnesses exist:

```powershell
docker compose up --build
.\scripts\smoke_mock_campaign.ps1
```

### E2E Tests

- E2E tests live in `frontend/e2e/`.
- E2E tests use Playwright against the local app and mocked backend/provider path.
- E2E tests must not require production auth, production providers, or production infrastructure.
- The E2E suite starts narrow and becomes mandatory as soon as the frontend route being tested exists.

Minimum E2E coverage by maturity:

- Baseline: app renders and can reach the local API health status through configured API URL.
- Auth: login/session restoration flow reaches the authenticated app shell using mock auth.
- Campaign creation: user enters category, selects discovered brand, starts campaign, and lands on dashboard.
- Dashboard: dashboard renders active status, polling stop on completion, metrics, citations, competitors, and prompt result rows.
- Regression: previous campaign can be reopened from campaign history.

Required command once harness exists:

```powershell
cd frontend
npx playwright test
```

## Mandatory Phase Gate

At the end of every phase in `plan.md`, run and record:

- Unit/API tests relevant to the files changed in the phase.
- Full backend `pytest` once backend harness exists.
- Full frontend `npm test`, `npm run lint`, and `npm run build` once frontend harness exists.
- Smoke test for the deepest runnable local workflow available at that phase.
- Playwright E2E for the deepest runnable browser workflow available at that phase.

The phase owner must update `PROGRESS.md` with:

- Phase number and name.
- Exact commands run.
- Pass/fail result.
- Any failing test names.
- Any intentionally deferred test layer and the exact next phase that will make it runnable.

## Safety Rules

- Run `scripts/check_no_prod_test_env.ps1` before smoke and E2E suites.
- Test settings must fail fast when `PROVIDER_MODE` is not `mock`.
- Test settings must fail fast when database or Redis URLs look like production Supabase or Redis Cloud endpoints.
- Test settings must fail fast when Gemini API keys are present during automated test runs.
- CI and local scripts must default to local Postgres, local Redis, mock auth, and mock providers.

## Final Release Verification

Before production readiness is marked complete, all of these must pass:

```powershell
cd backend
pytest
alembic upgrade head

cd ..\frontend
npm run lint
npm run build
npm test
npx playwright test

cd ..
.\scripts\check_no_prod_test_env.ps1
.\scripts\smoke_mock_campaign.ps1
.\scripts\deployment_check.ps1
```
