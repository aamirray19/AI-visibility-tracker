from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GROQ_API_KEY: str
    GOOGLE_AI_API_KEY: str

    DATABASE_URL: str

    REDIS_URL: str = "redis://localhost:6379"
    # Set a strong random secret: `python -c "import secrets; print(secrets.token_hex(32))"`
    API_SECRET_KEY: str = ""  

    FRONTEND_URL: str = "http://localhost:3000"

    WORKER_MAX_JOBS: int = Field(default=5, ge=1, le=20)
    RATE_LIMIT_SLEEP_SECONDS: float = Field(default=2.0, ge=0.0)

    PROMPT_TARGET_COUNT: int = Field(default=100, ge=1, le=500)

    DASHBOARD_CACHE_TTL_SECONDS: int = Field(default=3600, ge=60)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — loaded once at startup."""
    return Settings()

settings = get_settings()