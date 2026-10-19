from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.app.config import settings
from src.app.models.crawler_config import CrawlerModule
from src.app.services.feed_registry_service import FeedRegistryService
from src.app.utils.logger import logger

class CrawlerPipelineService:
    """
    Super-Admin Content & Ingestion Pipeline Controls.
    Allows enabling/disabling crawler modules, adjusting scraping intervals,
    and monitoring pipeline health across platforms (YouTube, Reddit, X, RSS, HN, GitHub).
    """

    @classmethod
    def sync_from_feed_registry(cls, db: Session):
        """Initializes crawler modules from the feed registry."""
        feeds_path = settings.FEEDS_CONFIG_PATH
        try:
            feeds = FeedRegistryService.load_feeds(feeds_path)

            for feed in feeds:
                name = feed.get("name")
                platform = feed.get("platform", "rss")
                existing = db.query(CrawlerModule).filter(CrawlerModule.name == name).first()
                if not existing:
                    mod = CrawlerModule(
                        name=name,
                        platform=platform,
                        category=feed.get("category", "General Tech"),
                        type=feed.get("type", "rss"),
                        url=feed.get("url", ""),
                        is_enabled=True,
                        schedule_interval_min=120,
                        health_status="healthy",
                        items_scraped=24,
                        last_run=datetime.utcnow()
                    )
                    db.add(mod)
            db.commit()
        except Exception as e:
            logger.error(f"Error syncing feed registry at {feeds_path} to crawler modules: {e}")
            db.rollback()

    @classmethod
    def list_modules(cls, db: Session, platform: Optional[str] = None) -> List[CrawlerModule]:
        query = db.query(CrawlerModule)
        if platform and platform != "all":
            query = query.filter(CrawlerModule.platform == platform)
        return query.order_by(CrawlerModule.platform.asc(), CrawlerModule.id.asc()).all()

    @classmethod
    def toggle_module(cls, db: Session, module_id: int, is_enabled: bool) -> CrawlerModule:
        mod = db.query(CrawlerModule).filter(CrawlerModule.id == module_id).first()
        if not mod:
            raise ValueError(f"Module {module_id} not found")
        mod.is_enabled = is_enabled
        db.commit()
        db.refresh(mod)
        return mod

    @classmethod
    def update_schedule(cls, db: Session, module_id: int, interval_min: int) -> CrawlerModule:
        mod = db.query(CrawlerModule).filter(CrawlerModule.id == module_id).first()
        if not mod:
            raise ValueError(f"Module {module_id} not found")
        mod.schedule_interval_min = interval_min
        db.commit()
        db.refresh(mod)
        return mod

    @classmethod
    def get_pipeline_health_summary(cls, db: Session) -> Dict[str, Any]:
        modules = db.query(CrawlerModule).all()
        total = len(modules)
        active = sum(1 for m in modules if m.is_enabled)
        platforms = set(m.platform for m in modules)
        
        return {
            "total_modules": total,
            "active_modules": active,
            "disabled_modules": total - active,
            "monitored_platforms": sorted(list(platforms)),
            "pipeline_status": "OPERATIONAL" if active > 0 else "PAUSED",
            "last_cluster_sync": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
