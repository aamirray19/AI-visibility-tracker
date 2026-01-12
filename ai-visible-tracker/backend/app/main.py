from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api import campaigns
from dotenv import load_dotenv
from app.core.db import init_db
import os

load_dotenv()

# Import models to register them with SQLModel
from app.models.campaign import Campaign, Prompt
from app.models.result import Result
from app.models.cited_url import CitedUrl
from app.models.competitor_mention import CompetitorMention

app = FastAPI(title="AI Campaign Tracker API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, allow all. stricter in prod.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.get("/")
def read_root():
    return {"message": "AI Campaign Tracker API is running"}

app.include_router(campaigns.router, prefix="/api", tags=["campaigns"])
