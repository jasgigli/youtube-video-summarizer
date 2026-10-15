from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class ChannelBase(BaseModel):
    title: str
    custom_url: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: int = 0
    is_active: bool = True

class ChannelCreate(BaseModel):
    # User can submit: channel URL (e.g. youtube.com/@veritasium), @handle, or direct channel ID
    input_identifier: str

class ChannelUpdate(BaseModel):
    is_active: Optional[bool] = None

class ChannelRead(ChannelBase):
    id: int
    channel_id: str
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    video_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)
