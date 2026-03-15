from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={
        "ssl": "require",
        "statement_cache_size": 0,
    },
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
