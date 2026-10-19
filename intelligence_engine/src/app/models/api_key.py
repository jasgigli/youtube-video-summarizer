from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from src.app.database import Base

class B2BApiKey(Base):
    __tablename__ = "b2b_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("saas_users.id", ondelete="SET NULL"), nullable=True)
    
    key_name = Column(String(128), nullable=False)
    api_key = Column(String(128), unique=True, index=True, nullable=False)
    rate_limit_per_min = Column(Integer, default=60)
    
    requests_total = Column(Integer, default=0)
    bandwidth_kb = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<B2BApiKey(id={self.id}, name='{self.key_name}', key='{self.api_key[:10]}...', active={self.is_active})>"
