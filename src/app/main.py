import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.app.config import settings
from src.app.database import engine, Base
from src.app.services.scheduler_service import scheduler_service
from src.app.utils.logger import logger
from src.app.routers import (
    channels_router,
    videos_router,
    summaries_router,
    jobs_router,
    settings_router,
    analytics_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database schema is initialized
    logger.info("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)
    
    # Start background scheduler
    logger.info("Booting background scheduler...")
    scheduler_service.start()
    
    yield
    
    # Shutdown
    logger.info("Stopping scheduler and releasing resources...")
    scheduler_service.shutdown()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Production-grade YouTube Subscriptions Ingestion, Transcript Fetcher & AI Summarizer",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(channels_router, prefix="/api")
app.include_router(videos_router, prefix="/api")
app.include_router(summaries_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION
    }

@app.get("/")
def root():
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "message": "YouTube Video Summarizer is running. Monitoring channels.json, categorizing latest videos, and generating rich Markdown (.md) digests into summaries/ every 2 hours."
    }
