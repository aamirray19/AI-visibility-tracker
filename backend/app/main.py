import re

import redis.asyncio as redis_asyncio
import sentry_sdk
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.v1 import companies, dashboard, profiles, prompts, scans, sources
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.deps import get_db, get_redis

configure_logging()

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

app = FastAPI(title="AI Visibility Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SCAN_ID_PATTERN = re.compile(r"/scans/([0-9a-fA-F-]{36})")


@app.middleware("http")
async def bind_scan_id(request: Request, call_next) -> Response:
    """§16: binds `scan_id` as the correlation id for every log line emitted
    while handling this request. Regex'd off the raw path rather than
    request.path_params, since BaseHTTPMiddleware runs before routing
    resolves path params."""
    match = _SCAN_ID_PATTERN.search(request.url.path)
    if match:
        bind_contextvars(scan_id=match.group(1))
    try:
        return await call_next(request)
    finally:
        clear_contextvars()


register_error_handlers(app)

app.include_router(companies.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(prompts.router, prefix="/api/v1")


@app.get("/health")
async def health(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: redis_asyncio.Redis = Depends(get_redis),
) -> dict:
    checks = {"database": "ok", "redis": "ok"}
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"
    try:
        await redis_client.ping()
    except Exception:
        checks["redis"] = "error"
    degraded = any(v == "error" for v in checks.values())
    if degraded:
        response.status_code = 503
    return {"status": "degraded" if degraded else "ok", "checks": checks}
