from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.app.database import get_db
from src.app.models.channel import Channel
from src.app.models.video import Video
from src.app.models.summary import Summary

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("")
def get_analytics(db: Session = Depends(get_db)):
    """Computes high-level intelligence and productivity metrics."""
    total_channels = db.query(Channel).count()
    total_videos = db.query(Video).count()
    summaries = db.query(Summary).all()
    total_summaries = len(summaries)
    
    # Calculate hours saved: assume ~14 minutes average consumption time per summarized video
    hours_saved = round((total_summaries * 14.0) / 60.0, 1)

    # Calculate token efficiency & topic counts
    total_tokens = sum(s.tokens_used or 0 for s in summaries)
    all_topics = []
    for s in summaries:
        all_topics.extend(s.topics)
    
    topic_counts = Counter(all_topics).most_common(8)
    formatted_topics = [{"name": t[0], "count": t[1]} for t in topic_counts]

    # Success rate
    failed_videos = db.query(Video).filter(Video.summary_status == "FAILED").count()
    success_rate = 100.0 if total_videos == 0 else round(
        ((total_videos - failed_videos) / total_videos) * 100, 1
    )

    return {
        "total_channels": total_channels,
        "total_videos": total_videos,
        "total_summaries": total_summaries,
        "hours_saved": hours_saved,
        "total_tokens_processed": total_tokens,
        "success_rate": success_rate,
        "top_topics": formatted_topics
    }
