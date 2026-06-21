# Decisions

## 2026-06-21: Phase 1 Baseline

- Use FastAPI for the API service with `/health` as the first public endpoint.
- Use Pydantic Settings to centralize environment configuration from the system design.
- Use Next.js with the App Router for the frontend baseline.
- Use local Docker Compose services for Postgres, Redis, API, worker placeholder, and frontend.
- Keep auth and provider modes mocked for local and test defaults until production configuration is added.
