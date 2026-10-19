import json
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from src.app.database import Base

class TeamMember(Base):
    __tablename__ = "workspace_members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    role = Column(String(32), default="Editor")  # Owner, Admin, Editor, Viewer
    avatar = Column(String(255), default="")
    status = Column(String(32), default="active")  # active, invited
    joined_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TeamMember(id={self.id}, name='{self.name}', role='{self.role}')>"

class ContentCalendarItem(Base):
    __tablename__ = "content_calendar_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    platform = Column(String(32), default="LinkedIn")  # X, LinkedIn, Reddit, Threads
    content = Column(Text, nullable=False)
    status = Column(String(32), default="pending", index=True)  # pending, approved, scheduled, published, rejected
    scheduled_at = Column(DateTime, nullable=True)
    author_name = Column(String(128), default="Antigravity Intelligence")
    tags_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def tags(self) -> List[str]:
        try:
            return json.loads(self.tags_json) if self.tags_json else []
        except Exception:
            return []

    @tags.setter
    def tags(self, val: List[str]):
        self.tags_json = json.dumps(val, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<ContentCalendarItem(id={self.id}, title='{self.title[:30]}...', status='{self.status}')>"

class WebhookIntegration(Base):
    __tablename__ = "workspace_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(32), nullable=False)  # slack, discord, teams
    webhook_url = Column(String(512), nullable=False)
    channel_name = Column(String(128), default="#general")
    is_enabled = Column(Boolean, default=True)
    topics_filter_json = Column(Text, default="[]")
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def topics_filter(self) -> List[str]:
        try:
            return json.loads(self.topics_filter_json) if self.topics_filter_json else []
        except Exception:
            return []

    @topics_filter.setter
    def topics_filter(self, val: List[str]):
        self.topics_filter_json = json.dumps(val, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<WebhookIntegration(id={self.id}, platform='{self.platform}', channel='{self.channel_name}')>"
