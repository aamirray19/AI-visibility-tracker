from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# ssl="require" for Supabase TLS.
# statement_cache_size=0 disables asyncpg prepared statement caching,
# which is REQUIRED when using Supabase's PgBouncer pooler (Transaction mode).
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args={
        "ssl": "require",
        "statement_cache_size": 0,
    },
)

# Shared session factory (used by both the API and the ARQ worker)
async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
