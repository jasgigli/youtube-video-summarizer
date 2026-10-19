import json
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean
from src.app.database import Base

class SaaSUser(Base):
    __tablename__ = "saas_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    tier = Column(String(32), default="free", index=True)  # free, pro, team, b2b_api, admin
    status = Column(String(32), default="active", index=True)  # active, suspended, cancelled
    billing_cycle = Column(String(32), default="monthly")  # monthly, yearly
    mrr = Column(Float, default=0.0)
    seats_count = Column(Integer, default=1)
    
    # Quota tracking
    daily_social_copies_used = Column(Integer, default=0)
    last_copy_reset = Column(DateTime, default=datetime.utcnow)
    
    # Pro/Enterprise customization
    custom_keywords_json = Column(Text, default="[]")
    auto_post_config_json = Column(Text, default="{}")
    
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def custom_keywords(self) -> List[str]:
        try:
            return json.loads(self.custom_keywords_json) if self.custom_keywords_json else []
        except Exception:
            return []

    @custom_keywords.setter
    def custom_keywords(self, val: List[str]):
        self.custom_keywords_json = json.dumps(val, ensure_ascii=False)

    @property
    def auto_post_config(self) -> Dict[str, Any]:
        try:
            return json.loads(self.auto_post_config_json) if self.auto_post_config_json else {}
        except Exception:
            return {}

    @auto_post_config.setter
    def auto_post_config(self, val: Dict[str, Any]):
        self.auto_post_config_json = json.dumps(val, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<SaaSUser(id={self.id}, email='{self.email}', tier='{self.tier}', status='{self.status}')>"
