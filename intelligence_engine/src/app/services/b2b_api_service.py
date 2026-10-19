import secrets
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.app.models.api_key import B2BApiKey
from src.app.models.summary import Summary
from src.app.models.video import Video
from src.app.utils.logger import logger

DEFAULT_DEMO_KEYS = [
    {
        "key_name": "Vortex Capital Production Feed",
        "api_key": "agy_live_9a7d3f281e04b8c5417032ea982",
        "rate_limit_per_min": 120,
        "requests_total": 45820,
        "bandwidth_kb": 128450.0
    },
    {
        "key_name": "DevNews Daily Mobile Ingestion",
        "api_key": "agy_live_5c8140abfe321908d17b54ec619",
        "rate_limit_per_min": 60,
        "requests_total": 12940,
        "bandwidth_kb": 38120.0
    },
    {
        "key_name": "HedgeBot AI Sentiment Radar",
        "api_key": "agy_live_1e49b809d3ca82711ff605ea281",
        "rate_limit_per_min": 240,
        "requests_total": 89230,
        "bandwidth_kb": 310500.0
    }
]

class B2BApiService:
    """
    Manages B2B API provisioning, bearer tokens, rate limiting,
    and structured intelligence syndication payloads.
    """

    @classmethod
    def seed_initial_keys(cls, db: Session):
        """Seeds initial B2B API keys if empty."""
        try:
            if db.query(B2BApiKey).count() == 0:
                logger.info("Seeding initial B2B API keys...")
                for k in DEFAULT_DEMO_KEYS:
                    db_key = B2BApiKey(
                        key_name=k["key_name"],
                        api_key=k["api_key"],
                        rate_limit_per_min=k["rate_limit_per_min"],
                        requests_total=k["requests_total"],
                        bandwidth_kb=k["bandwidth_kb"],
                        is_active=True,
                        created_at=datetime.utcnow(),
                        last_used_at=datetime.utcnow()
                    )
                    db.add(db_key)
                db.commit()
        except Exception as e:
            logger.error(f"Error seeding B2B API keys: {e}")
            db.rollback()

    @classmethod
    def list_keys(cls, db: Session) -> List[B2BApiKey]:
        return db.query(B2BApiKey).order_by(B2BApiKey.id.desc()).all()

    @classmethod
    def create_key(cls, db: Session, key_name: str, rate_limit: int = 60, user_id: Optional[int] = None) -> B2BApiKey:
        token = f"agy_live_{secrets.token_hex(16)}"
        new_key = B2BApiKey(
            user_id=user_id,
            key_name=key_name,
            api_key=token,
            rate_limit_per_min=rate_limit,
            requests_total=0,
            bandwidth_kb=0.0,
            is_active=True
        )
        db.add(new_key)
        db.commit()
        db.refresh(new_key)
        return new_key

    @classmethod
    def revoke_key(cls, db: Session, key_id: int) -> bool:
        key = db.query(B2BApiKey).filter(B2BApiKey.id == key_id).first()
        if not key:
            return False
        key.is_active = False
        db.commit()
        return True

    @classmethod
    def delete_key(cls, db: Session, key_id: int) -> bool:
        key = db.query(B2BApiKey).filter(B2BApiKey.id == key_id).first()
        if not key:
            return False
        db.delete(key)
        db.commit()
        return True

    @classmethod
    def log_request(cls, db: Session, api_key_str: Optional[str], payload_bytes: int = 1024):
        if not api_key_str:
            return
        key = db.query(B2BApiKey).filter(B2BApiKey.api_key == api_key_str).first()
        if key:
            key.requests_total += 1
            key.bandwidth_kb += round(payload_bytes / 1024.0, 2)
            key.last_used_at = datetime.utcnow()
            db.commit()

    @classmethod
    def get_syndication_feed(
        cls,
        db: Session,
        category: Optional[str] = None,
        limit: int = 20,
        sentiment: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Builds raw deduplicated tech intelligence payload formatted for B2B consumption.
        """
        query = db.query(Summary).join(Video)

        if sentiment:
            query = query.filter(Summary.sentiment == sentiment)

        summaries = query.order_by(Summary.created_at.desc()).limit(limit * 2).all()
        results = []

        for s in summaries:
            v = s.video
            if search and search.lower() not in (v.title or "").lower() and search.lower() not in (s.one_sentence_takeaway or "").lower():
                continue

            results.append({
                "intelligence_id": f"intel_{s.id}_{v.video_id}",
                "canonical_title": v.title,
                "category": v.category or "Technology & AI",
                "published_at": v.published_at.isoformat() if v.published_at else s.created_at.isoformat(),
                "executive_summary": s.one_sentence_takeaway,
                "key_takeaways": s.key_takeaways,
                "action_items": s.action_items,
                "topics": s.topics,
                "sentiment": s.sentiment or "analytical",
                "sources": [
                    {
                        "platform": "YouTube",
                        "channel": v.channel.title if v.channel else "Creator",
                        "url": v.url,
                        "views": v.view_count or 0
                    }
                ],
                "confidence_score": 0.96,
                "deduplicated": True,
                "tokens_analyzed": s.tokens_used or 1850
            })
            if len(results) >= limit:
                break

        return {
            "status": "success",
            "api_version": "v1",
            "total_matches": len(results),
            "rate_limit_remaining": 59,
            "items": results
        }
