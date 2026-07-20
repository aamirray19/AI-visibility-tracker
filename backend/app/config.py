from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    database_url: str
    redis_url: str
    api_key: str
    cors_origins: str = "http://localhost:5173"
    sentry_dsn: str = ""  # §16: empty disables Sentry (dev/test default)

    # Key pools (§10.1). Comma-separated: id:secret:org
    google_exec_keys: str = ""
    google_flash_keys: str = ""
    groq_exec_keys: str = ""
    groq_eval_a_keys: str = ""
    groq_eval_b_keys: str = ""

    pool_google_exec_strategy: str = "round_robin"
    pool_google_flash_strategy: str = "failover"
    pool_groq_exec_strategy: str = "round_robin"
    pool_groq_eval_a_strategy: str = "round_robin"
    pool_groq_eval_b_strategy: str = "round_robin"
    rate_limit_scope: str = "key"

    # Models
    model_enrichment: str = "gemini-2.5-flash"
    model_verification: str = "gemini-2.5-flash"
    model_prompt_gen: str = "gemini-2.5-flash"
    model_evaluation: str = "llama-3.3-70b-versatile"
    model_exec_google: str = "gemma-4-31b-it"
    model_exec_groq: str = "openai/gpt-oss-120b"

    # Pipeline
    prompt_count: int = 50
    worker_max_jobs: int = 20
    llm_timeout_s: int = 60
    llm_cache_ttl: int = 0
    scan_reuse_ttl_hours: int = 1
    scan_purge_after_days: int = 0
    scan_success_threshold: float = 0.70
    eval_max_defer_s: int = 900

    # Limits
    adaptive_rate_limit: bool = True
    rate_limit_cold_start_rpm: int = 20
    rate_limit_cold_start_tpm: int = 5000
    max_pool_spins: int = 20
    scan_cost_ceiling_usd: float = 2.00
    daily_cost_ceiling_usd: float = 20.00


settings = Settings()
