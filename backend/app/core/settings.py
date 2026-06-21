from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_visibility",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_key_prefix: str = Field(default="ait:local", alias="REDIS_KEY_PREFIX")
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")
    worker_max_jobs: int = Field(default=5, alias="WORKER_MAX_JOBS")
    dashboard_cache_ttl_seconds: int = Field(default=1200, alias="DASHBOARD_CACHE_TTL_SECONDS")

    auth_mode: str = Field(default="mock", alias="AUTH_MODE")
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_jwks_url: str | None = Field(default=None, alias="SUPABASE_JWKS_URL")
    supabase_jwt_audience: str | None = Field(default=None, alias="SUPABASE_JWT_AUDIENCE")
    supabase_project_ref: str | None = Field(default=None, alias="SUPABASE_PROJECT_REF")

    provider_mode: str = Field(default="mock", alias="PROVIDER_MODE")
    gemini_discovery_api_key: str | None = Field(default=None, alias="GEMINI_DISCOVERY_API_KEY")
    gemini_prompt_api_key: str | None = Field(default=None, alias="GEMINI_PROMPT_API_KEY")
    gemini_grounded_search_api_key: str | None = Field(
        default=None,
        alias="GEMINI_GROUNDED_SEARCH_API_KEY",
    )
    gemini_analysis_api_key: str | None = Field(default=None, alias="GEMINI_ANALYSIS_API_KEY")
    gemini_discovery_model: str | None = Field(default=None, alias="GEMINI_DISCOVERY_MODEL")
    gemini_prompt_model: str | None = Field(default=None, alias="GEMINI_PROMPT_MODEL")
    gemini_grounded_search_model: str | None = Field(
        default=None,
        alias="GEMINI_GROUNDED_SEARCH_MODEL",
    )
    gemini_analysis_model: str | None = Field(default=None, alias="GEMINI_ANALYSIS_MODEL")

    test_database_url: str | None = Field(default=None, alias="TEST_DATABASE_URL")
    test_redis_url: str | None = Field(default=None, alias="TEST_REDIS_URL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
