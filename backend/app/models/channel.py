from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    custom_url = Column(String(128), nullable=True)  # e.g., @mkbhd
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    subscriber_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, title='{self.title}', channel_id='{self.channel_id}')>"
