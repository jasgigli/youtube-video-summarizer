from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

@dataclass
class OmnichannelItem:
    """Standardized ingested data model across all platforms."""
    id: str
    platform: str                    # "youtube" | "reddit" | "hackernews" | "github" | "blog" | "frontier_ai" | "twitch" | "vimeo"
    source_name: str                 # e.g. "Reddit r/LocalLLaMA", "TechCrunch AI", "OpenAI Research", "Fireship"
    title: str
    url: str
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    content_text: str = ""           # Full body, transcript, README, or description
    summary_hint: str = ""           # Short snippet or excerpt
    category: str = "general_tech"   # "ai_frontier" | "software_engineering" | "open_source" | "big_tech" | "hardware_chips" | "startups_vc"
    engagement: Dict[str, Any] = field(default_factory=dict) # e.g. {"upvotes": 450, "comments_count": 82, "stars": 1200}
    community_comments: List[Dict[str, str]] = field(default_factory=list) # [{"author": "dev1", "text": "...", "score": 25}]
    tags: List[str] = field(default_factory=list)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform,
            "source_name": self.source_name,
            "title": self.title,
            "url": self.url,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "content_text": self.content_text,
            "summary_hint": self.summary_hint,
            "category": self.category,
            "engagement": self.engagement,
            "community_comments": self.community_comments,
            "tags": self.tags
        }

class BaseAdapter(ABC):
    """Abstract base class for all omnichannel ingestion adapters."""

    @abstractmethod
    async def fetch_items(self, feed_config: Dict[str, Any], limit: int = 5) -> List[OmnichannelItem]:
        """Fetches latest items from the specified source feed."""
        pass
