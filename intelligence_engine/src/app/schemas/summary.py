from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class NotableQuote(BaseModel):
    quote: str
    context_or_timestamp: Optional[str] = None

class SummaryBase(BaseModel):
    provider: str
    model_name: str
    one_sentence_takeaway: str
    key_takeaways: List[str] = Field(default_factory=list)
    detailed_breakdown: str
    action_items: List[str] = Field(default_factory=list)
    notable_quotes: List[NotableQuote] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    sentiment: str = "informative"
    tokens_used: int = 0
    processing_time_sec: float = 0.0

class SummaryRead(BaseModel):
    id: int
    video_id: int
    provider: str
    model_name: str
    one_sentence_takeaway: str
    key_takeaways: List[str] = Field(default_factory=list)
    detailed_breakdown: str
    action_items: List[str] = Field(default_factory=list)
    notable_quotes: List[Dict[str, Any]] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    sentiment: str
    tokens_used: int
    processing_time_sec: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SummaryRegenerateRequest(BaseModel):
    custom_instruction: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
