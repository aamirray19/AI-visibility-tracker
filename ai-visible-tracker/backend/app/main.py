from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import campaigns
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="AI Campaign Tracker API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, allow all. Restrict in prod.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    # Tables are managed via the Supabase SQL Editor — no auto-creation here.
    print("AI Campaign Tracker API started. Connected to Supabase.")

@app.get("/")
def read_root():
    return {"message": "AI Campaign Tracker API is running"}

app.include_router(campaigns.router, prefix="/api", tags=["campaigns"])
