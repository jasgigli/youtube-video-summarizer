from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from src.app.schemas.summary import SummaryRead

class VideoBase(BaseModel):
    video_id: str
    title: str
    description: Optional[str] = None
    published_at: datetime
    thumbnail_url: Optional[str] = None
    duration_seconds: int = 0
    video_url: str

class VideoRead(VideoBase):
    id: int
    channel_id: int
    channel_title: Optional[str] = None
    transcript_status: str
    transcript_language: Optional[str] = None
    transcript_error: Optional[str] = None
    summary_status: str
    summary_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    summary: Optional[SummaryRead] = None

    model_config = ConfigDict(from_attributes=True)
