import os
from arq.connections import RedisSettings

# Supports redis:// (local) and rediss:// (Redis Cloud with TLS + password)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_settings = RedisSettings.from_dsn(REDIS_URL)
