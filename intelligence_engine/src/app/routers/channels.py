from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from src.app.database import get_db
from src.app.models.channel import Channel
from src.app.models.video import Video
from src.app.models.setting import Setting
from src.app.schemas.channel import ChannelCreate, ChannelRead, ChannelUpdate
from src.app.services.youtube_service import YouTubeService
from src.app.services.job_service import JobService
from src.app.utils.logger import logger

router = APIRouter(prefix="/channels", tags=["Channels"])

@router.get("", response_model=List[ChannelRead])
def list_channels(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """Retrieve all tracked YouTube channels with video counters."""
    query = db.query(Channel)
    if active_only:
        query = query.filter(Channel.is_active == True)
    
    channels = query.order_by(Channel.created_at.desc()).all()
    results = []
    for ch in channels:
        v_count = db.query(Video).filter(Video.channel_id == ch.id).count()
        item = ChannelRead.model_validate(ch)
        item.video_count = v_count
        results.append(item)
    return results

@router.post("", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
async def add_channel(
    payload: ChannelCreate,
    db: Session = Depends(get_db)
):
    """
    Resolve YouTube URL or @handle, store the channel,
    and automatically queue initial sync of recent videos.
    """
    api_key_setting = db.query(Setting).filter(Setting.key == "youtube_api_key").first()
    yt_service = YouTubeService(api_key=api_key_setting.value if api_key_setting else None)

    try:
        resolved = await yt_service.resolve_channel(payload.input_identifier)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to resolve channel: {str(e)}"
        )

    # Check if already added
    existing = db.query(Channel).filter(Channel.channel_id == resolved["channel_id"]).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel '{existing.title}' is already being tracked."
        )

    channel = Channel(
        channel_id=resolved["channel_id"],
        title=resolved["title"],
        custom_url=resolved.get("custom_url"),
        description=resolved.get("description"),
        thumbnail_url=resolved.get("thumbnail_url"),
        subscriber_count=resolved.get("subscriber_count", 0),
        is_active=True
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Trigger automatic background sync for the newly added channel
    await JobService.create_and_run_job("SYNC_CHANNEL", str(channel.id))

    item = ChannelRead.model_validate(channel)
    item.video_count = 0
    return item

@router.patch("/{channel_id}", response_model=ChannelRead)
def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    db: Session = Depends(get_db)
):
    """Toggle active status or update channel preferences."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if payload.is_active is not None:
        channel.is_active = payload.is_active

    db.commit()
    db.refresh(channel)
    v_count = db.query(Video).filter(Video.channel_id == channel.id).count()
    item = ChannelRead.model_validate(channel)
    item.video_count = v_count
    return item

@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db)
):
    """Delete a tracked channel and all associated videos and summaries."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    db.delete(channel)
    db.commit()
    return None

@router.post("/{channel_id}/sync")
async def trigger_channel_sync(
    channel_id: int,
    db: Session = Depends(get_db)
):
    """Manually triggers background sync for a specific channel."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    job_uuid = await JobService.create_and_run_job("SYNC_CHANNEL", str(channel.id))
    return {"message": f"Sync queued for '{channel.title}'", "job_uuid": job_uuid}
