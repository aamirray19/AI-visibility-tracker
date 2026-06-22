# Decisions

## 2026-06-21: Phase 1 Baseline

- Use FastAPI for the API service with `/health` as the first public endpoint.
- Use Pydantic Settings to centralize environment configuration from the system design.
- Use Next.js with the App Router for the frontend baseline.
- Use local Docker Compose services for Postgres, Redis, API, worker placeholder, and frontend.
- Keep auth and provider modes mocked for local and test defaults until production configuration is added.

## 2026-06-22: Phase 2 Schema And Migrations

- Use SQLModel models as the application schema definition, with Alembic migrations as the database source of truth.
- Keep campaign status derived from prompt states instead of storing a campaign status column.
- Use PostgreSQL-compatible Alembic configuration, but allow SQLite-backed migration execution in automated tests.
- Store the `cited_url.metadata` database column through the Python attribute `metadata_json` because `metadata` is reserved by SQLAlchemy declarative models.
- Add `psycopg` as the migration-time PostgreSQL driver while keeping `asyncpg` for runtime async sessions.
