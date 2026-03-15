from arq.connections import RedisSettings
from app.core.config import settings

redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)