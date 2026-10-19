from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from src.app.database import Base

class NewsletterDispatch(Base):
    __tablename__ = "newsletter_dispatches"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    provider = Column(String(32), default="beehiiv")  # beehiiv, convertkit
    content_markdown = Column(Text, nullable=False)
    status = Column(String(32), default="draft")  # draft, scheduled, sent
    subscriber_count = Column(Integer, default=14250)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<NewsletterDispatch(id={self.id}, title='{self.title}', status='{self.status}', provider='{self.provider}')>"
