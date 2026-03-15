"""
FastAPI application entry point.
Includes: Bearer token auth, CORS restriction, rate limiting, health endpoint.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import campaigns
from app.core.config import settings
from app.core.limiter import limiter

#Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


#Auth helper
_bearer = HTTPBearer(auto_error=False)


def require_auth(credentials: HTTPAuthorizationCredentials = Security(_bearer)):
    """
    Bearer-token guard. Skipped entirely when API_SECRET_KEY is empty (dev mode).
    Set API_SECRET_KEY in .env to enable.
    """
    if not settings.API_SECRET_KEY:
        return  # auth disabled in dev
    if credentials is None or credentials.credentials != settings.API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


#App lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BrandSight AI API starting up")
    yield
    logger.info("BrandSight AI API shutting down")


#App
app = FastAPI(
    title="BrandSight AI – Campaign Tracker API",
    description="Track brand visibility across AI platforms.",
    version="1.0.0",
    lifespan=lifespan,
)

#Rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#Root endpoint
@app.get("/", tags=["system"])
async def root():
    return {
        "message": "Welcome to BrandSight AI API. Visit /docs for documentation.",
        "status": "active"
    }


#Health endpoint
@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


#Routes
app.include_router(
    campaigns.router,
    prefix="/api",
    tags=["campaigns"],
    dependencies=[Security(require_auth)],  
)
