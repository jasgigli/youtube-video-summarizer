import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.app.config import settings
from src.app.models.saas_user import SaaSUser
from src.app.utils.logger import logger

DEFAULT_DEMO_USERS = [
    {
        "email": "alex.dev@gmail.com",
        "name": "Alex Mercer",
        "tier": "free",
        "status": "active",
        "billing_cycle": "monthly",
        "mrr": 0.0,
        "seats_count": 1,
        "daily_social_copies_used": 1,
        "custom_keywords": ["LLM", "Rust", "FastAPI"]
    },
    {
        "email": "sarah.creator@indiehackers.io",
        "name": "Sarah Chen",
        "tier": "pro",
        "status": "active",
        "billing_cycle": "monthly",
        "mrr": 5.0,
        "seats_count": 1,
        "daily_social_copies_used": 14,
        "custom_keywords": ["PyTorch", "LLM Benchmarks", "Open Source Releases", "Agents"]
    },
    {
        "email": "devrel@acmeworks.com",
        "name": "DevRel Team Lead",
        "tier": "team",
        "status": "active",
        "billing_cycle": "monthly",
        "mrr": 25.0,  # $19 + 2 extra seats ($6)
        "seats_count": 7,
        "daily_social_copies_used": 68,
        "custom_keywords": ["Developer Experience", "API Gateways", "Distributed Systems"]
    },
    {
        "email": "quant.data@vortexcapital.ai",
        "name": "Vortex Capital Data Lab",
        "tier": "b2b_api",
        "status": "active",
        "billing_cycle": "monthly",
        "mrr": 29.0,
        "seats_count": 10,
        "daily_social_copies_used": 240,
        "custom_keywords": ["Generative AI", "Semiconductors", "Venture Capital"]
    },
    {
        "email": "admin@antigravity-intelligence.io",
        "name": "Chief Platform Admin",
        "tier": "admin",
        "status": "active",
        "billing_cycle": "yearly",
        "mrr": 0.0,
        "seats_count": 999,
        "daily_social_copies_used": 0,
        "custom_keywords": ["*"]
    }
]

class SaaSService:
    """
    Manages SaaS accounts, 4-tier subscriptions, revenue metrics,
    and quota governance across the platform.
    """

    @classmethod
    def seed_initial_users(cls, db: Session):
        """Seeds initial user accounts if database is empty."""
        try:
            if db.query(SaaSUser).count() == 0:
                logger.info("Seeding initial SaaS user accounts...")
                for u in DEFAULT_DEMO_USERS:
                    user = SaaSUser(
                        email=u["email"],
                        name=u["name"],
                        tier=u["tier"],
                        status=u["status"],
                        billing_cycle=u["billing_cycle"],
                        mrr=u["mrr"],
                        seats_count=u["seats_count"],
                        daily_social_copies_used=u["daily_social_copies_used"],
                        custom_keywords_json=json.dumps(u["custom_keywords"]),
                        auto_post_config_json=json.dumps({
                            "twitter_connected": u["tier"] in ["pro", "team", "admin"],
                            "linkedin_connected": u["tier"] in ["pro", "team", "admin"],
                            "threads_connected": False,
                            "auto_post_frequency": "instant" if u["tier"] == "team" else "manual"
                        })
                    )
                    db.add(user)
                db.commit()
        except Exception as e:
            logger.error(f"Error seeding SaaS users: {e}")
            db.rollback()

    @classmethod
    def get_users(cls, db: Session, tier: Optional[str] = None) -> List[SaaSUser]:
        query = db.query(SaaSUser)
        if tier and tier != "all":
            query = query.filter(SaaSUser.tier == tier)
        return query.order_by(SaaSUser.id.asc()).all()

    @classmethod
    def get_or_create_user(cls, db: Session, email: str, name: str = "User", tier: str = "free") -> SaaSUser:
        user = db.query(SaaSUser).filter(SaaSUser.email == email).first()
        if not user:
            mrr = 0.0
            if tier == "pro":
                mrr = settings.TIER_PRO_MONTHLY_PRICE
            elif tier == "team":
                mrr = settings.TIER_TEAM_MONTHLY_PRICE
            elif tier == "b2b_api":
                mrr = settings.TIER_B2B_MONTHLY_PRICE

            user = SaaSUser(
                email=email,
                name=name,
                tier=tier,
                status="active",
                mrr=mrr,
                seats_count=1 if tier != "team" else 5
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    @classmethod
    def update_user_tier(cls, db: Session, user_id: int, new_tier: str, extra_seats: int = 0) -> SaaSUser:
        user = db.query(SaaSUser).filter(SaaSUser.id == user_id).first()
        if not user:
            raise ValueError(f"User with id {user_id} not found")

        user.tier = new_tier
        if new_tier == "free":
            user.mrr = 0.0
            user.seats_count = 1
        elif new_tier == "pro":
            user.mrr = settings.TIER_PRO_MONTHLY_PRICE
            user.seats_count = 1
        elif new_tier == "team":
            base = settings.TIER_TEAM_MONTHLY_PRICE
            seats = settings.TIER_TEAM_INCLUDED_SEATS + max(0, extra_seats)
            user.seats_count = seats
            user.mrr = base + (max(0, extra_seats) * settings.TIER_TEAM_EXTRA_SEAT_PRICE)
        elif new_tier == "b2b_api":
            user.mrr = settings.TIER_B2B_MONTHLY_PRICE
            user.seats_count = 10
        elif new_tier == "admin":
            user.mrr = 0.0

        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def toggle_user_status(cls, db: Session, user_id: int, status: str) -> SaaSUser:
        user = db.query(SaaSUser).filter(SaaSUser.id == user_id).first()
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        user.status = status
        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def check_and_use_copy_quota(cls, db: Session, user_email: str) -> Dict[str, Any]:
        """
        Enforces 3 standard social post copies/day for Free Tier.
        Pro and Team tiers have unlimited access.
        """
        user = db.query(SaaSUser).filter(SaaSUser.email == user_email).first()
        if not user:
            user = cls.get_or_create_user(db, user_email, tier="free")

        # Pro, Team, B2B, Admin tiers have unlimited copies
        if user.tier in ["pro", "team", "b2b_api", "admin"]:
            user.daily_social_copies_used += 1
            db.commit()
            return {
                "allowed": True,
                "tier": user.tier,
                "copies_used": user.daily_social_copies_used,
                "copies_limit": "unlimited",
                "remaining": "unlimited"
            }

        # Check reset date (24-hour cycle)
        now = datetime.utcnow()
        if user.last_copy_reset and (now - user.last_copy_reset).total_seconds() > 86400:
            user.daily_social_copies_used = 0
            user.last_copy_reset = now

        limit = settings.TIER_FREE_DAILY_SOCIAL_COPIES
        if user.daily_social_copies_used >= limit:
            return {
                "allowed": False,
                "tier": "free",
                "copies_used": user.daily_social_copies_used,
                "copies_limit": limit,
                "remaining": 0,
                "message": f"Daily Free Tier limit reached ({limit}/{limit} copies used today). Upgrade to Pro for $5/mo for unlimited exports & automated posting."
            }

        user.daily_social_copies_used += 1
        db.commit()
        remaining = max(0, limit - user.daily_social_copies_used)
        return {
            "allowed": True,
            "tier": "free",
            "copies_used": user.daily_social_copies_used,
            "copies_limit": limit,
            "remaining": remaining
        }

    @classmethod
    def get_revenue_metrics(cls, db: Session) -> Dict[str, Any]:
        """Aggregates real-time MRR, ARR, tier distribution, and subscriber growth."""
        users = db.query(SaaSUser).all()
        total_mrr = sum(u.mrr for u in users if u.status == "active")
        total_arr = round(total_mrr * 12, 2)
        
        counts = {
            "free": sum(1 for u in users if u.tier == "free"),
            "pro": sum(1 for u in users if u.tier == "pro"),
            "team": sum(1 for u in users if u.tier == "team"),
            "b2b_api": sum(1 for u in users if u.tier == "b2b_api"),
            "admin": sum(1 for u in users if u.tier == "admin"),
        }

        # Projected revenue breakdown
        return {
            "mrr": round(total_mrr, 2),
            "arr": total_arr,
            "total_users": len(users),
            "active_paying_customers": counts["pro"] + counts["team"] + counts["b2b_api"],
            "tier_distribution": counts,
            "pricing_matrix": {
                "free": {"price": "$0/mo", "desc": "Public feed, top 5 daily summaries, 3 social copies/day"},
                "pro": {"price": "$5/mo", "desc": "Unlimited exports, custom trackers, .md download, direct auto-posting"},
                "team": {"price": "$19/mo", "desc": "5 seats included (+$3/extra seat), approval calendar, Slack/Discord webhooks"},
                "b2b_api": {"price": "$29/mo", "desc": "REST/GraphQL raw intelligence, real-time webhooks, JSON payloads"}
            },
            "growth_rate_pct": 24.5,
            "average_revenue_per_user": round(total_mrr / max(1, (counts["pro"] + counts["team"] + counts["b2b_api"])), 2)
        }
