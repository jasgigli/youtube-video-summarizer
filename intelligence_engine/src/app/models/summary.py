import json
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.app.database import Base

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    provider = Column(String(32), default="gemini")
    model_name = Column(String(64), nullable=False)
    
    # Structured Insights
    one_sentence_takeaway = Column(String(512), nullable=False)
    key_takeaways_json = Column(Text, default="[]")       # List[str]
    detailed_breakdown = Column(Text, nullable=False)        # Markdown content
    action_items_json = Column(Text, default="[]")         # List[str]
    notable_quotes_json = Column(Text, default="[]")       # List[Dict[str, str]] (quote, speaker/timestamp)
    topics_json = Column(Text, default="[]")               # List[str]
    sentiment = Column(String(32), default="informative")
    
    # Metrics
    tokens_used = Column(Integer, default=0)
    processing_time_sec = Column(Float, default=0.0)
    custom_prompt_used = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    video = relationship("Video", back_populates="summary")

    # Helper property accessors for JSON fields
    @property
    def key_takeaways(self) -> List[str]:
        try:
            return json.loads(self.key_takeaways_json) if self.key_takeaways_json else []
        except Exception:
            return []

    @key_takeaways.setter
    def key_takeaways(self, val: List[str]):
        self.key_takeaways_json = json.dumps(val, ensure_ascii=False)

    @property
    def action_items(self) -> List[str]:
        try:
            return json.loads(self.action_items_json) if self.action_items_json else []
        except Exception:
            return []

    @action_items.setter
    def action_items(self, val: List[str]):
        self.action_items_json = json.dumps(val, ensure_ascii=False)

    @property
    def notable_quotes(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.notable_quotes_json) if self.notable_quotes_json else []
        except Exception:
            return []

    @notable_quotes.setter
    def notable_quotes(self, val: List[Dict[str, Any]]):
        self.notable_quotes_json = json.dumps(val, ensure_ascii=False)

    @property
    def topics(self) -> List[str]:
        try:
            return json.loads(self.topics_json) if self.topics_json else []
        except Exception:
            return []

    @topics.setter
    def topics(self, val: List[str]):
        self.topics_json = json.dumps(val, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<Summary(id={self.id}, video_id={self.video_id}, model='{self.model_name}')>"
