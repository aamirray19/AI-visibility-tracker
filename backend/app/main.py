from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import companies, scans
from app.config import settings
from app.core.errors import register_error_handlers

app = FastAPI(title="AI Visibility Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(companies.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
