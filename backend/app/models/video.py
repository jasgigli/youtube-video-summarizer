from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String(32), unique=True, index=True, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=False, index=True)
    thumbnail_url = Column(String(512), nullable=True)
    duration_seconds = Column(Integer, default=0)
    video_url = Column(String(256), nullable=False)

    # Transcript state
    # Transcript statuses: PENDING, SUCCESS, UNAVAILABLE, DISABLED, ERROR
    transcript_status = Column(String(32), default="PENDING", index=True)
    transcript_text = Column(Text, nullable=True)
    transcript_error = Column(Text, nullable=True)
    transcript_language = Column(String(16), nullable=True)

    # Summary state
    # Summary statuses: PENDING, PROCESSING, COMPLETED, SKIPPED, FAILED
    summary_status = Column(String(32), default="PENDING", index=True)
    summary_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    channel = relationship("Channel", back_populates="videos")
    summary = relationship("Summary", back_populates="video", uselist=False, cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, video_id='{self.video_id}', title='{self.title[:30]}...')>"
