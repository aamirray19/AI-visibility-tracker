import hmac
from collections.abc import AsyncGenerator

import redis.asyncio as redis_asyncio
from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.error_codes import UNAUTHORIZED
from app.core.errors import AppError

engine = create_async_engine(settings.database_url)
_session_maker = async_sessionmaker(engine, expire_on_commit=False)

_redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise AppError(UNAUTHORIZED, "Missing or invalid X-API-Key", status_code=401)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_maker() as session:
        yield session


async def get_redis() -> redis_asyncio.Redis:
    return _redis_client
