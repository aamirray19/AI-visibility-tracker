from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.core.errors import register_error_handlers
from app.core.redis import get_redis
from app.db.session import engine

app = FastAPI(title="AI Brand Monitoring Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)


@app.get("/health")
async def health():
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    redis = get_redis()
    await redis.ping()
    return {"status": "ok"}
