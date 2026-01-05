import os
from arq.connections import RedisSettings

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Parse redis url
if "://" not in REDIS_URL:
    REDIS_HOST = REDIS_URL
    REDIS_PORT = 6379
else:
    # simple parsing, assuming standard redis://host:port/db
    parts = REDIS_URL.replace("redis://", "").split(":")
    REDIS_HOST = parts[0]
    if len(parts) > 1:
        REDIS_PORT = int(parts[1].split("/")[0])
    else:
        REDIS_PORT = 6379

redis_settings = RedisSettings(host=REDIS_HOST, port=REDIS_PORT)
