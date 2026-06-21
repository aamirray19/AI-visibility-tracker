from datetime import UTC, datetime

from fastapi import FastAPI

from app.core.settings import get_settings


settings = get_settings()
app = FastAPI(title="AI Visibility Tracker API", version=settings.app_version)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "version": settings.app_version,
    }
