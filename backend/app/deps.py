import hmac
from collections.abc import AsyncGenerator

import redis.asyncio as redis_asyncio
from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.error_codes import UNAUTHORIZED
from app.core.errors import AppError

engine = create_async_engine(settings.database_url)
_session_maker = async_sessionmaker(engine, expire_on_commit=False)

_redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)

_arq_pool: ArqRedis | None = None


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise AppError(UNAUTHORIZED, "Missing or invalid X-API-Key", status_code=401)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_maker() as session:
        yield session


async def get_redis() -> redis_asyncio.Redis:
    return _redis_client


async def get_arq_redis() -> ArqRedis:
    """Lazily-created ARQ connection pool, separate from the plain redis
    client above -- enqueue_job() is arq-specific and needs its own pool.
    Defaults to the interactive queue, since every job the API layer enqueues
    directly (enrich_company, verify_profile) is human-gated (§8) -- ARQ's
    own default queue name would silently strand jobs nothing is consuming."""
    global _arq_pool
    if _arq_pool is None:
        from app.worker.queues import INTERACTIVE_QUEUE

        _arq_pool = await create_pool(
            RedisSettings.from_dsn(settings.redis_url), default_queue_name=INTERACTIVE_QUEUE
        )
    return _arq_pool
