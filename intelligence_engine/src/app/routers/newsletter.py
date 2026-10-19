from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.app.database import get_db
from src.app.services.newsletter_dispatcher_service import NewsletterDispatcherService

router = APIRouter(prefix="/newsletter", tags=["Newsletter Dispatcher"])

class NewsletterGenerateRequest(BaseModel):
    title: str = "Daily Tech & AI Executive Digest"
    provider: str = "beehiiv"

class NewsletterBroadcastRequest(BaseModel):
    provider: Optional[str] = "beehiiv"

@router.get("/drafts")
def list_newsletters(db: Session = Depends(get_db)):
    """List auto-generated and dispatched newsletter digests."""
    NewsletterDispatcherService.seed_initial_drafts(db)
    dispatches = NewsletterDispatcherService.list_dispatches(db)
    return {
        "count": len(dispatches),
        "dispatches": [
            {
                "id": d.id,
                "title": d.title,
                "subject": d.subject,
                "provider": d.provider,
                "content_markdown": d.content_markdown,
                "status": d.status,
                "subscriber_count": d.subscriber_count,
                "sent_at": d.sent_at.strftime("%Y-%m-%d %H:%M UTC") if d.sent_at else None,
                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else None
            }
            for d in dispatches
        ]
    }

@router.post("/generate")
def generate_digest(payload: NewsletterGenerateRequest, db: Session = Depends(get_db)):
    """Auto-assembles the latest top 5 summaries into an executive newsletter draft."""
    draft = NewsletterDispatcherService.generate_digest_draft(db, title=payload.title, provider=payload.provider)
    return {
        "message": "Newsletter draft generated successfully",
        "id": draft.id,
        "title": draft.title,
        "subject": draft.subject,
        "provider": draft.provider,
        "content_preview": draft.content_markdown[:300]
    }

@router.post("/{dispatch_id}/broadcast")
def broadcast_newsletter(dispatch_id: int, payload: NewsletterBroadcastRequest, db: Session = Depends(get_db)):
    """Simulates broadcasting the approved newsletter to email subscribers via Beehiiv or ConvertKit."""
    try:
        return NewsletterDispatcherService.broadcast_newsletter(db, dispatch_id=dispatch_id, provider=payload.provider)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
