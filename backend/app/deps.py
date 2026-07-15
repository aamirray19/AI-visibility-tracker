import hmac

from fastapi import Header

from app.config import settings
from app.core.errors import AppError


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise AppError("UNAUTHORIZED", "Missing or invalid X-API-Key", status_code=401)
