from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.app.database import get_db
from src.app.services.crawler_pipeline_service import CrawlerPipelineService

router = APIRouter(prefix="/crawlers", tags=["Ingestion & Crawler Pipeline"])

class ToggleRequest(BaseModel):
    is_enabled: bool

class ScheduleRequest(BaseModel):
    interval_min: int

@router.get("/modules")
def list_crawler_modules(platform: Optional[str] = None, db: Session = Depends(get_db)):
    """List crawler and ingestion modules with on/off status and statistics."""
    CrawlerPipelineService.sync_from_feed_registry(db)
    modules = CrawlerPipelineService.list_modules(db, platform=platform)
    return {
        "count": len(modules),
        "modules": [
            {
                "id": m.id,
                "name": m.name,
                "platform": m.platform,
                "category": m.category,
                "type": m.type,
                "url": m.url,
                "is_enabled": m.is_enabled,
                "schedule_interval_min": m.schedule_interval_min,
                "health_status": m.health_status,
                "items_scraped": m.items_scraped,
                "last_run": m.last_run.strftime("%Y-%m-%d %H:%M") if m.last_run else "Pending"
            }
            for m in modules
        ]
    }

@router.patch("/modules/{module_id}/toggle")
def toggle_crawler_module(module_id: int, payload: ToggleRequest, db: Session = Depends(get_db)):
    """Enable or disable a specific crawler module (YouTube, Reddit, X, HN, RSS)."""
    try:
        mod = CrawlerPipelineService.toggle_module(db, module_id=module_id, is_enabled=payload.is_enabled)
        state_str = "ENABLED" if mod.is_enabled else "DISABLED"
        return {"message": f"Crawler '{mod.name}' is now {state_str}", "module_id": mod.id, "is_enabled": mod.is_enabled}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/modules/{module_id}/schedule")
def update_crawler_schedule(module_id: int, payload: ScheduleRequest, db: Session = Depends(get_db)):
    """Adjust the scraping schedule interval in minutes."""
    try:
        mod = CrawlerPipelineService.update_schedule(db, module_id=module_id, interval_min=payload.interval_min)
        return {"message": f"Scrape schedule for '{mod.name}' set to every {mod.schedule_interval_min} minutes", "interval_min": mod.schedule_interval_min}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/health")
def get_pipeline_health(db: Session = Depends(get_db)):
    """Pipeline health overview and crawler module metrics."""
    CrawlerPipelineService.sync_from_feed_registry(db)
    return CrawlerPipelineService.get_pipeline_health_summary(db)
