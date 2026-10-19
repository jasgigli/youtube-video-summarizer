from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.app.models.newsletter import NewsletterDispatch
from src.app.models.summary import Summary
from src.app.models.video import Video
from src.app.utils.logger import logger

class NewsletterDispatcherService:
    """
    Super-Admin Newsletter Dispatcher.
    Synthesizes daily/weekly summaries into ready-to-broadcast newsletters,
    formats markdown, and simulates direct email broadcasts to Beehiiv and ConvertKit.
    """

    @classmethod
    def seed_initial_drafts(cls, db: Session):
        try:
            if db.query(NewsletterDispatch).count() == 0:
                logger.info("Seeding initial newsletter drafts...")
                sample_draft = NewsletterDispatch(
                    title="Daily AI & Frontier Tech Intelligence — Oct 19, 2026",
                    subject="🔥 DeepSeek V4.1 Leaks, Multi-Agent Swarms Surge & Anthropic Workforce Update",
                    provider="beehiiv",
                    content_markdown="""# 🚀 Daily Tech & AI Executive Briefing

Good morning! Here are the highest-impact breakthroughs from across the global technology and AI ecosystem today:

---

### 1. Multi-Agent Coding Swarms Surge on GitHub Trending
* **Core Specs:** Distributed consensus protocols and deterministic tool-calling frameworks are overtaking monolithic LLM agents.
* **Industry Impact:** Developer signups jumped 320% as teams adopt agentic pair programming loops.

### 2. DeepSeek V4.1 Flash Uncensored GGUF Variants Emerge
* **Details:** 4-bit quantizations retain 98.2% reasoning fidelity while slashing VRAM requirements from 48GB to 14GB.
* **Community Reaction:** Intense excitement on Reddit r/LocalLLaMA over local edge workstation deployment.

---

*Curated automatically by the Omnichannel Intelligence Engine.*
""",
                    status="draft",
                    subscriber_count=14250,
                    created_at=datetime.utcnow()
                )
                db.add(sample_draft)
                db.commit()
        except Exception as e:
            logger.error(f"Error seeding newsletter drafts: {e}")
            db.rollback()

    @classmethod
    def list_dispatches(cls, db: Session) -> List[NewsletterDispatch]:
        return db.query(NewsletterDispatch).order_by(NewsletterDispatch.created_at.desc()).all()

    @classmethod
    def generate_digest_draft(cls, db: Session, title: str, provider: str = "beehiiv") -> NewsletterDispatch:
        """Auto-assembles the latest top 5 summaries into a ready-to-broadcast newsletter draft."""
        top_summaries = db.query(Summary).join(Video).order_by(Summary.created_at.desc()).limit(5).all()

        lines = [
            f"# 📡 {title}",
            f"*Dispatched via Omnichannel Intelligence Engine — {datetime.utcnow().strftime('%B %d, %Y')}*\n",
            "Here are today's top technical breakthroughs and architectural shifts:\n",
            "---"
        ]

        for idx, s in enumerate(top_summaries, 1):
            v = s.video
            channel = v.channel.title if v.channel else "Tech Intelligence"
            lines.append(f"### {idx}. {v.title}")
            lines.append(f"**Source:** {channel} | **Category:** {v.category or 'AI'}")
            lines.append(f"> {s.one_sentence_takeaway}\n")
            if s.key_takeaways:
                lines.append("**Key Takeaways:**")
                for pt in s.key_takeaways[:3]:
                    lines.append(f"* 🔹 {pt}")
            lines.append(f"\n[Read Source Discussion & Documentation]({v.url})\n---")

        content = "\n".join(lines)
        dispatch = NewsletterDispatch(
            title=title,
            subject=f"⚡ Executive Tech Brief: {top_summaries[0].video.title[:45]}...",
            provider=provider,
            content_markdown=content,
            status="draft",
            subscriber_count=14250
        )
        db.add(dispatch)
        db.commit()
        db.refresh(dispatch)
        return dispatch

    @classmethod
    def broadcast_newsletter(cls, db: Session, dispatch_id: int, provider: Optional[str] = None) -> Dict[str, Any]:
        """Dispatches newsletter to external email platform (Beehiiv / ConvertKit)."""
        dispatch = db.query(NewsletterDispatch).filter(NewsletterDispatch.id == dispatch_id).first()
        if not dispatch:
            raise ValueError("Newsletter draft not found")

        if provider:
            dispatch.provider = provider
        dispatch.status = "sent"
        dispatch.sent_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "dispatch_id": dispatch.id,
            "title": dispatch.title,
            "subject": dispatch.subject,
            "provider": dispatch.provider,
            "recipients_delivered": dispatch.subscriber_count,
            "delivery_timestamp": dispatch.sent_at.isoformat(),
            "message": f"Successfully broadcasted to {dispatch.subscriber_count:,} active subscribers via {dispatch.provider.upper()} API."
        }
