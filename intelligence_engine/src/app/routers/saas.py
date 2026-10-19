import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from src.app.database import get_db
from src.app.models.saas_user import SaaSUser
from src.app.services.saas_service import SaaSService

router = APIRouter(prefix="/saas", tags=["SaaS & Subscriptions"])

class UserCreateRequest(BaseModel):
    email: str
    name: str
    tier: str = "free"
    billing_cycle: str = "monthly"

class TierUpdateRequest(BaseModel):
    tier: str
    extra_seats: int = 0

class StatusUpdateRequest(BaseModel):
    status: str

class KeywordUpdateRequest(BaseModel):
    email: str
    keywords: List[str]

class AutoPostSettingsRequest(BaseModel):
    email: str
    twitter_connected: bool = True
    linkedin_connected: bool = True
    threads_connected: bool = False
    frequency: str = "instant"

@router.get("/users")
def list_users(tier: Optional[str] = None, db: Session = Depends(get_db)):
    """List SaaS users with optional filtering by tier."""
    SaaSService.seed_initial_users(db)
    users = SaaSService.get_users(db, tier=tier)
    return {
        "count": len(users),
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "tier": u.tier,
                "status": u.status,
                "billing_cycle": u.billing_cycle,
                "mrr": u.mrr,
                "seats_count": u.seats_count,
                "daily_social_copies_used": u.daily_social_copies_used,
                "custom_keywords": u.custom_keywords,
                "auto_post_config": u.auto_post_config,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ]
    }

@router.post("/users")
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db)):
    """Create a new user or subscribe to a plan."""
    user = SaaSService.get_or_create_user(db, email=payload.email, name=payload.name, tier=payload.tier)
    return {"message": "User registered successfully", "user_id": user.id, "tier": user.tier, "mrr": user.mrr}

@router.patch("/users/{user_id}/tier")
def update_tier(user_id: int, payload: TierUpdateRequest, db: Session = Depends(get_db)):
    """Super-Admin tier override or user upgrade/downgrade."""
    try:
        user = SaaSService.update_user_tier(db, user_id=user_id, new_tier=payload.tier, extra_seats=payload.extra_seats)
        return {
            "message": f"User {user.email} successfully transitioned to {user.tier.upper()} tier",
            "tier": user.tier,
            "mrr": user.mrr,
            "seats": user.seats_count
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/users/{user_id}/status")
def update_status(user_id: int, payload: StatusUpdateRequest, db: Session = Depends(get_db)):
    """Super-Admin account suspension or activation."""
    try:
        user = SaaSService.toggle_user_status(db, user_id=user_id, status=payload.status)
        return {"message": f"User {user.email} status updated to {user.status}", "status": user.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/quota/check")
def check_quota(email: str = Query("alex.dev@gmail.com"), db: Session = Depends(get_db)):
    """Checks remaining daily social post copies."""
    SaaSService.seed_initial_users(db)
    user = db.query(SaaSUser).filter(SaaSUser.email == email).first()
    if not user:
        user = SaaSService.get_or_create_user(db, email, tier="free")
    
    if user.tier in ["pro", "team", "b2b_api", "admin"]:
        return {
            "tier": user.tier,
            "is_unlimited": True,
            "copies_used": user.daily_social_copies_used,
            "remaining": 999999,
            "limit": "unlimited"
        }
    
    limit = 3
    remaining = max(0, limit - user.daily_social_copies_used)
    return {
        "tier": "free",
        "is_unlimited": False,
        "copies_used": user.daily_social_copies_used,
        "remaining": remaining,
        "limit": limit
    }

@router.post("/quota/use-copy")
def use_social_copy(email: str = Body(..., embed=True), db: Session = Depends(get_db)):
    """Increments social copy count and enforces 3-copy daily limit for free tier."""
    SaaSService.seed_initial_users(db)
    result = SaaSService.check_and_use_copy_quota(db, user_email=email)
    if not result["allowed"]:
        raise HTTPException(status_code=429, detail=result["message"])
    return result

@router.get("/revenue")
def get_revenue_analytics(db: Session = Depends(get_db)):
    """Super-Admin revenue, MRR, ARR, and subscriber growth."""
    SaaSService.seed_initial_users(db)
    return SaaSService.get_revenue_metrics(db)

@router.post("/trackers/keywords")
def save_custom_keywords(payload: KeywordUpdateRequest, db: Session = Depends(get_db)):
    """Pro Tier custom keyword tracking additions."""
    user = db.query(SaaSUser).filter(SaaSUser.email == payload.email).first()
    if not user:
        user = SaaSService.get_or_create_user(db, payload.email, tier="pro")
    user.custom_keywords = payload.keywords
    db.commit()
    return {"message": "Custom keyword trackers saved", "keywords": user.custom_keywords}

@router.post("/autopost/settings")
def save_autopost_settings(payload: AutoPostSettingsRequest, db: Session = Depends(get_db)):
    """Pro Tier personal social OAuth tokens & auto-publishing settings."""
    user = db.query(SaaSUser).filter(SaaSUser.email == payload.email).first()
    if not user:
        user = SaaSService.get_or_create_user(db, payload.email, tier="pro")
    user.auto_post_config = {
        "twitter_connected": payload.twitter_connected,
        "linkedin_connected": payload.linkedin_connected,
        "threads_connected": payload.threads_connected,
        "frequency": payload.frequency
    }
    db.commit()
    return {"message": "Social media auto-posting connections updated", "config": user.auto_post_config}
