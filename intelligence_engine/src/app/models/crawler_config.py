from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from src.app.database import Base

class CrawlerModule(Base):
    __tablename__ = "crawler_modules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    platform = Column(String(64), nullable=False, index=True)
    category = Column(String(128), default="General Tech")
    type = Column(String(32), default="rss")  # rss, hn_api, reddit_json, youtube_feed, github_trending
    url = Column(String(512), nullable=False)
    is_enabled = Column(Boolean, default=True)
    schedule_interval_min = Column(Integer, default=120)
    health_status = Column(String(32), default="healthy")  # healthy, degraded, failed
    items_scraped = Column(Integer, default=0)
    last_run = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<CrawlerModule(id={self.id}, name='{self.name}', platform='{self.platform}', enabled={self.is_enabled})>"
