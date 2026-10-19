import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.app.models.workspace import TeamMember, ContentCalendarItem, WebhookIntegration
from src.app.utils.logger import logger

DEFAULT_MEMBERS = [
    {
        "name": "Marcus Vance",
        "email": "marcus.v@acmeworks.com",
        "role": "Owner",
        "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80",
        "status": "active"
    },
    {
        "name": "Elena Rostova",
        "email": "elena.r@acmeworks.com",
        "role": "Admin",
        "avatar": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=100&auto=format&fit=crop&q=80",
        "status": "active"
    },
    {
        "name": "Devon Taylor",
        "email": "devon.t@acmeworks.com",
        "role": "Editor",
        "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80",
        "status": "active"
    },
    {
        "name": "Priya Sharma",
        "email": "priya.s@acmeworks.com",
        "role": "Viewer",
        "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&auto=format&fit=crop&q=80",
        "status": "active"
    }
]

DEFAULT_CALENDAR_ITEMS = [
    {
        "title": "Anthropic Claude 3.5 Sonnet Coding Benchmark Analysis",
        "platform": "LinkedIn",
        "content": "🚀 Deep dive into the latest benchmark results: Claude 3.5 Sonnet demonstrates a 14% uplift on complex SWE-bench tasks. Here is what software architecture teams must evaluate...",
        "status": "scheduled",
        "author_name": "Devon Taylor",
        "scheduled_at": datetime.utcnow() + timedelta(hours=4)
    },
    {
        "title": "Open Source Multi-Agent Swarms on GitHub Trending",
        "platform": "X",
        "content": "1/ 🚨 Multi-agent coding swarms jumped +320% on GitHub Trending this week.\n\n2/ Key highlights: distributed context windows and deterministic tool-calling frameworks are overtaking monolithic agents.\n\n3/ Full breakdown below #AI #SoftwareEngineering",
        "status": "approved",
        "author_name": "Elena Rostova",
        "scheduled_at": datetime.utcnow() + timedelta(days=1)
    },
    {
        "title": "DeepSeek V4.1 Flash Architectural Memory Optimization",
        "platform": "Reddit",
        "content": "Title: DeepSeek V4.1 Flash Uncensored GGUF Variants Emerge: Technical Breakdown\nBody: Community benchmarks confirm 4-bit quantizations retain 98.2% reasoning accuracy while cutting VRAM footprint from 48GB to 14GB.",
        "status": "pending",
        "author_name": "Marcus Vance",
        "scheduled_at": None
    }
]

DEFAULT_WEBHOOKS = [
    {
        "platform": "slack",
        "channel_name": "#engineering-intel",
        "webhook_url": "https://hooks.slack.com/services/T000/B000/sampleSlackToken99",
        "is_enabled": True,
        "topics_filter": ["AI Agents", "System Design", "Releases"]
    },
    {
        "platform": "discord",
        "channel_name": "#ai-breaking-news",
        "webhook_url": "https://discord.com/api/webhooks/123456789/sampleDiscordWebhookToken",
        "is_enabled": True,
        "topics_filter": ["Frontier AI", "Open Source"]
    },
    {
        "platform": "teams",
        "channel_name": "Tech Architecture Watch",
        "webhook_url": "https://acme.webhook.office.com/webhookb2/sampleMSTeamsWebhook",
        "is_enabled": False,
        "topics_filter": ["Semiconductors", "Enterprise AI"]
    }
]

class TeamWorkspaceService:
    """
    Manages Enterprise & Team Workspaces:
    - Member roles (Owner, Admin, Editor, Viewer)
    - Content calendar approval workflow (pending -> approved -> scheduled -> published)
    - Webhook integrations (Slack, Discord, MS Teams)
    """

    @classmethod
    def seed_initial_workspace(cls, db: Session):
        """Seeds initial team members, content calendar items, and webhooks if empty."""
        try:
            if db.query(TeamMember).count() == 0:
                logger.info("Seeding initial workspace members...")
                for m in DEFAULT_MEMBERS:
                    db.add(TeamMember(
                        name=m["name"],
                        email=m["email"],
                        role=m["role"],
                        avatar=m["avatar"],
                        status=m["status"],
                        joined_at=datetime.utcnow()
                    ))
                db.commit()

            if db.query(ContentCalendarItem).count() == 0:
                logger.info("Seeding initial content calendar items...")
                for c in DEFAULT_CALENDAR_ITEMS:
                    db.add(ContentCalendarItem(
                        title=c["title"],
                        platform=c["platform"],
                        content=c["content"],
                        status=c["status"],
                        author_name=c["author_name"],
                        scheduled_at=c["scheduled_at"],
                        tags_json=json.dumps(["AI", "Engineering", "Production"])
                    ))
                db.commit()

            if db.query(WebhookIntegration).count() == 0:
                logger.info("Seeding initial workspace webhooks...")
                for w in DEFAULT_WEBHOOKS:
                    db.add(WebhookIntegration(
                        platform=w["platform"],
                        channel_name=w["channel_name"],
                        webhook_url=w["webhook_url"],
                        is_enabled=w["is_enabled"],
                        topics_filter_json=json.dumps(w["topics_filter"])
                    ))
                db.commit()
        except Exception as e:
            logger.error(f"Error seeding workspace data: {e}")
            db.rollback()

    # Members
    @classmethod
    def list_members(cls, db: Session) -> List[TeamMember]:
        return db.query(TeamMember).order_by(TeamMember.id.asc()).all()

    @classmethod
    def add_member(cls, db: Session, name: str, email: str, role: str = "Editor") -> TeamMember:
        member = TeamMember(
            name=name,
            email=email,
            role=role,
            avatar="https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&auto=format&fit=crop&q=80",
            status="active"
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        return member

    @classmethod
    def update_member_role(cls, db: Session, member_id: int, role: str) -> TeamMember:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
        if not member:
            raise ValueError(f"Member with id {member_id} not found")
        member.role = role
        db.commit()
        db.refresh(member)
        return member

    @classmethod
    def remove_member(cls, db: Session, member_id: int) -> bool:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
        if not member:
            return False
        db.delete(member)
        db.commit()
        return True

    # Calendar
    @classmethod
    def list_calendar_items(cls, db: Session, status: Optional[str] = None) -> List[ContentCalendarItem]:
        query = db.query(ContentCalendarItem)
        if status and status != "all":
            query = query.filter(ContentCalendarItem.status == status)
        return query.order_by(ContentCalendarItem.created_at.desc()).all()

    @classmethod
    def add_calendar_item(
        cls,
        db: Session,
        title: str,
        platform: str,
        content: str,
        author_name: str = "Team Member",
        scheduled_at: Optional[datetime] = None
    ) -> ContentCalendarItem:
        item = ContentCalendarItem(
            title=title,
            platform=platform,
            content=content,
            author_name=author_name,
            status="pending",
            scheduled_at=scheduled_at or (datetime.utcnow() + timedelta(days=1))
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def update_calendar_status(cls, db: Session, item_id: int, new_status: str) -> ContentCalendarItem:
        item = db.query(ContentCalendarItem).filter(ContentCalendarItem.id == item_id).first()
        if not item:
            raise ValueError(f"Calendar item {item_id} not found")
        item.status = new_status
        db.commit()
        db.refresh(item)
        return item

    # Webhooks
    @classmethod
    def list_webhooks(cls, db: Session) -> List[WebhookIntegration]:
        return db.query(WebhookIntegration).all()

    @classmethod
    def add_or_update_webhook(
        cls,
        db: Session,
        platform: str,
        channel_name: str,
        webhook_url: str,
        topics: List[str]
    ) -> WebhookIntegration:
        wh = db.query(WebhookIntegration).filter(WebhookIntegration.platform == platform).first()
        if not wh:
            wh = WebhookIntegration(platform=platform)
            db.add(wh)
        wh.channel_name = channel_name
        wh.webhook_url = webhook_url
        wh.topics_filter_json = json.dumps(topics)
        wh.is_enabled = True
        db.commit()
        db.refresh(wh)
        return wh

    @classmethod
    def test_webhook_dispatch(cls, db: Session, webhook_id: int) -> Dict[str, Any]:
        wh = db.query(WebhookIntegration).filter(WebhookIntegration.id == webhook_id).first()
        if not wh:
            raise ValueError("Webhook not found")
        wh.last_triggered_at = datetime.utcnow()
        db.commit()
        return {
            "status": "success",
            "platform": wh.platform,
            "channel": wh.channel_name,
            "message": f"Simulated test alert sent to {wh.platform.upper()} channel {wh.channel_name}",
            "payload_preview": {
                "title": "⚡ Real-Time Intelligence Alert: OpenAI Releases New Frontier Model",
                "summary": "DeepMind and Anthropic announce joint evaluation safety protocols across autonomous agent swarms.",
                "url": "http://localhost:8000"
            }
        }
