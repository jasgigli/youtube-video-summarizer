import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.app.config import settings
from src.app.database import engine, Base, SessionLocal, get_db
from src.app.services.scheduler_service import scheduler_service
from src.app.services.saas_service import SaaSService
from src.app.services.b2b_api_service import B2BApiService
from src.app.services.team_workspace_service import TeamWorkspaceService
from src.app.services.crawler_pipeline_service import CrawlerPipelineService
from src.app.services.newsletter_dispatcher_service import NewsletterDispatcherService
from src.app.models.summary import Summary
from src.app.models.video import Video
from src.app.utils.logger import logger
from src.app.routers import (
    channels_router,
    videos_router,
    summaries_router,
    jobs_router,
    settings_router,
    analytics_router,
    omnichannel_router,
    saas_router,
    b2b_router,
    workspace_router,
    crawlers_router,
    newsletter_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database schema is initialized
    logger.info("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)

    # Seed initial SaaS, B2B keys, Team Workspace, and Crawler pipeline data
    logger.info("Seeding initial SaaS and pipeline data...")
    db = SessionLocal()
    try:
        SaaSService.seed_initial_users(db)
        B2BApiService.seed_initial_keys(db)
        TeamWorkspaceService.seed_initial_workspace(db)
        CrawlerPipelineService.sync_from_feed_registry(db)
        NewsletterDispatcherService.seed_initial_drafts(db)
    except Exception as e:
        logger.error(f"Error seeding initial data: {e}")
    finally:
        db.close()
    
    # Start background scheduler
    logger.info("Booting background scheduler...")
    scheduler_service.start()
    
    yield
    
    # Shutdown
    logger.info("Stopping scheduler and releasing resources...")
    scheduler_service.shutdown()

app = FastAPI(
    title="Multi-Tier Omnichannel Intelligence Platform & Global Admin Infrastructure",
    version=settings.VERSION,
    description="Enterprise-grade AI intelligence engine continuously ingesting, deduplicating, and summarizing tech/AI breakthroughs with a 4-Tier SaaS architecture and Super-Admin Command Dashboard.",
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
app.include_router(saas_router, prefix="/api")
app.include_router(b2b_router)  # Handles /api/v1/...
app.include_router(workspace_router, prefix="/api")
app.include_router(crawlers_router, prefix="/api")
app.include_router(newsletter_router, prefix="/api")
app.include_router(omnichannel_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(channels_router, prefix="/api")
app.include_router(videos_router, prefix="/api")
app.include_router(summaries_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(settings_router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "saas_tiers": ["Free ($0)", "Pro ($5/mo)", "Team ($19/mo)", "B2B API ($29/mo)", "Super-Admin"]
    }

@app.get("/api/intelligence/latest-top5")
def get_daily_top5(db: Session = Depends(get_db)):
    """Curates top 5 daily tech and AI summaries for the Free Public Web App."""
    summaries = db.query(Summary).join(Video).order_by(Summary.created_at.desc()).limit(5).all()
    results = []
    for s in summaries:
        v = s.video
        results.append({
            "id": s.id,
            "video_id": v.video_id,
            "title": v.title,
            "channel": v.channel.title if v.channel else "Tech Intelligence",
            "category": v.category or "Artificial Intelligence",
            "executive_summary": s.one_sentence_takeaway,
            "key_takeaways": s.key_takeaways[:3],
            "action_items": s.action_items[:2],
            "url": v.url,
            "published_at": v.published_at.strftime("%b %d, %Y") if v.published_at else s.created_at.strftime("%b %d, %Y"),
            "sentiment": s.sentiment or "analytical"
        })
    return {"status": "success", "count": len(results), "top_5": results}

