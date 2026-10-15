from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from backend.app.database import get_db
from backend.app.models.video import Video
from backend.app.models.channel import Channel
from backend.app.schemas.video import VideoRead
from backend.app.schemas.summary import SummaryRead
from backend.app.services.job_service import JobService

router = APIRouter(prefix="/videos", tags=["Videos"])

@router.get("", response_model=List[VideoRead])
def list_videos(
    channel_id: Optional[int] = Query(None, description="Filter by channel DB ID"),
    summary_status: Optional[str] = Query(None, description="Filter by status: COMPLETED, PENDING, SKIPPED, FAILED"),
    query: Optional[str] = Query(None, description="Search term in title or description"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List videos with rich filtering and search capabilities."""
    stmt = db.query(Video).join(Channel, Video.channel_id == Channel.id)

    if channel_id:
        stmt = stmt.filter(Video.channel_id == channel_id)
    if summary_status:
        stmt = stmt.filter(Video.summary_status == summary_status.upper())
    if query:
        search_pattern = f"%{query}%"
        stmt = stmt.filter(
            or_(
                Video.title.ilike(search_pattern),
                Video.description.ilike(search_pattern),
                Channel.title.ilike(search_pattern)
            )
        )

    videos = stmt.order_by(desc(Video.published_at)).offset(offset).limit(limit).all()
    
    results = []
    for v in videos:
        v_read = VideoRead(
            id=v.id,
            video_id=v.video_id,
            channel_id=v.channel_id,
            channel_title=v.channel.title if v.channel else None,
            title=v.title,
            description=v.description,
            published_at=v.published_at,
            thumbnail_url=v.thumbnail_url,
            duration_seconds=v.duration_seconds,
            video_url=v.video_url,
            transcript_status=v.transcript_status,
            transcript_language=v.transcript_language,
            transcript_error=v.transcript_error,
            summary_status=v.summary_status,
            summary_error=v.summary_error,
            created_at=v.created_at,
            updated_at=v.updated_at,
            summary=SummaryRead.model_validate(v.summary) if v.summary else None
        )
        results.append(v_read)

    return results

@router.get("/{video_id}", response_model=VideoRead)
def get_video_detail(
    video_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve full details for a video including transcript status and summary."""
    v = db.query(Video).filter(Video.id == video_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")

    return VideoRead(
        id=v.id,
        video_id=v.video_id,
        channel_id=v.channel_id,
        channel_title=v.channel.title if v.channel else None,
        title=v.title,
        description=v.description,
        published_at=v.published_at,
        thumbnail_url=v.thumbnail_url,
        duration_seconds=v.duration_seconds,
        video_url=v.video_url,
        transcript_status=v.transcript_status,
        transcript_language=v.transcript_language,
        transcript_error=v.transcript_error,
        summary_status=v.summary_status,
        summary_error=v.summary_error,
        created_at=v.created_at,
        updated_at=v.updated_at,
        summary=SummaryRead.model_validate(v.summary) if v.summary else None
    )

@router.get("/{video_id}/transcript")
def get_video_transcript(
    video_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve raw or formatted transcript text."""
    v = db.query(Video).filter(Video.id == video_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "video_id": v.video_id,
        "title": v.title,
        "status": v.transcript_status,
        "language": v.transcript_language,
        "error": v.transcript_error,
        "transcript": v.transcript_text or ""
    }

@router.post("/{video_id}/summarize")
async def trigger_summarize(
    video_id: int,
    db: Session = Depends(get_db)
):
    """Queue video for transcript fetching and AI summarization."""
    v = db.query(Video).filter(Video.id == video_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")

    job_uuid = await JobService.create_and_run_job("SUMMARIZE_VIDEO", str(v.id))
    return {"message": f"Summarization queued for '{v.title}'", "job_uuid": job_uuid}

@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: int,
    db: Session = Depends(get_db)
):
    """Remove video and associated summary from database."""
    v = db.query(Video).filter(Video.id == video_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")

    db.delete(v)
    db.commit()
    return None
