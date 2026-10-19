from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.app.database import get_db
from src.app.services.team_workspace_service import TeamWorkspaceService

router = APIRouter(prefix="/workspace", tags=["Team & Enterprise Workspace"])

class MemberAddRequest(BaseModel):
    name: str
    email: str
    role: str = "Editor"

class MemberRoleUpdateRequest(BaseModel):
    role: str

class CalendarItemCreateRequest(BaseModel):
    title: str
    platform: str
    content: str
    author_name: str = "DevRel Lead"
    scheduled_at: Optional[datetime] = None

class CalendarStatusUpdateRequest(BaseModel):
    status: str  # pending, approved, scheduled, published, rejected

class WebhookConfigureRequest(BaseModel):
    platform: str  # slack, discord, teams
    channel_name: str
    webhook_url: str
    topics: List[str]

# MEMBERS
@router.get("/members")
def get_members(db: Session = Depends(get_db)):
    """List team members and roles."""
    TeamWorkspaceService.seed_initial_workspace(db)
    members = TeamWorkspaceService.list_members(db)
    return {
        "count": len(members),
        "seats_included": 5,
        "seats_used": len(members),
        "members": [
            {
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "role": m.role,
                "avatar": m.avatar,
                "status": m.status,
                "joined_at": m.joined_at.strftime("%b %d, %Y") if m.joined_at else ""
            }
            for m in members
        ]
    }

@router.post("/members")
def invite_member(payload: MemberAddRequest, db: Session = Depends(get_db)):
    """Invite a new team member."""
    member = TeamWorkspaceService.add_member(db, name=payload.name, email=payload.email, role=payload.role)
    return {"message": f"Invitation sent to {member.email}", "member_id": member.id, "role": member.role}

@router.patch("/members/{member_id}/role")
def change_member_role(member_id: int, payload: MemberRoleUpdateRequest, db: Session = Depends(get_db)):
    """Update granular team role (Owner, Admin, Editor, Viewer)."""
    try:
        member = TeamWorkspaceService.update_member_role(db, member_id=member_id, role=payload.role)
        return {"message": f"Updated {member.name}'s role to {member.role}", "role": member.role}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/members/{member_id}")
def delete_member(member_id: int, db: Session = Depends(get_db)):
    """Remove a team member."""
    success = TeamWorkspaceService.remove_member(db, member_id=member_id)
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "Member removed successfully"}

# CALENDAR
@router.get("/calendar")
def get_calendar_items(status: Optional[str] = None, db: Session = Depends(get_db)):
    """List content calendar items with approval status filter."""
    TeamWorkspaceService.seed_initial_workspace(db)
    items = TeamWorkspaceService.list_calendar_items(db, status=status)
    return {
        "count": len(items),
        "items": [
            {
                "id": i.id,
                "title": i.title,
                "platform": i.platform,
                "content": i.content,
                "status": i.status,
                "author_name": i.author_name,
                "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
                "created_at": i.created_at.strftime("%Y-%m-%d %H:%M") if i.created_at else None
            }
            for i in items
        ]
    }

@router.post("/calendar")
def create_calendar_item(payload: CalendarItemCreateRequest, db: Session = Depends(get_db)):
    """Add a generated intelligence post to the shared calendar queue."""
    item = TeamWorkspaceService.add_calendar_item(
        db,
        title=payload.title,
        platform=payload.platform,
        content=payload.content,
        author_name=payload.author_name,
        scheduled_at=payload.scheduled_at
    )
    return {"message": "Item queued in content calendar", "id": item.id, "status": item.status}

@router.patch("/calendar/{item_id}/status")
def update_item_status(item_id: int, payload: CalendarStatusUpdateRequest, db: Session = Depends(get_db)):
    """Transition post status (pending -> approved -> scheduled -> published)."""
    try:
        item = TeamWorkspaceService.update_calendar_status(db, item_id=item_id, new_status=payload.status)
        return {"message": f"Calendar item updated to {item.status.upper()}", "status": item.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# WEBHOOKS
@router.get("/webhooks")
def list_webhooks(db: Session = Depends(get_db)):
    """List configured outgoing webhooks (Slack, Discord, MS Teams)."""
    TeamWorkspaceService.seed_initial_workspace(db)
    webhooks = TeamWorkspaceService.list_webhooks(db)
    return {
        "count": len(webhooks),
        "webhooks": [
            {
                "id": w.id,
                "platform": w.platform,
                "channel_name": w.channel_name,
                "webhook_url": f"{w.webhook_url[:24]}...{w.webhook_url[-6:]}",
                "full_url": w.webhook_url,
                "is_enabled": w.is_enabled,
                "topics_filter": w.topics_filter,
                "last_triggered_at": w.last_triggered_at.strftime("%Y-%m-%d %H:%M") if w.last_triggered_at else "Never"
            }
            for w in webhooks
        ]
    }

@router.post("/webhooks")
def configure_webhook(payload: WebhookConfigureRequest, db: Session = Depends(get_db)):
    """Add or update an outgoing webhook."""
    wh = TeamWorkspaceService.add_or_update_webhook(
        db,
        platform=payload.platform,
        channel_name=payload.channel_name,
        webhook_url=payload.webhook_url,
        topics=payload.topics
    )
    return {"message": f"{payload.platform.upper()} webhook configured", "id": wh.id}

@router.post("/webhooks/{webhook_id}/test")
def test_webhook(webhook_id: int, db: Session = Depends(get_db)):
    """Broadcasts a simulated real-time intelligence test alert to the webhook."""
    try:
        return TeamWorkspaceService.test_webhook_dispatch(db, webhook_id=webhook_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
