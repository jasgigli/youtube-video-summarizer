import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import feedparser
import httpx
from src.app.services.adapters.base_adapter import BaseAdapter, OmnichannelItem
from src.app.utils.logger import logger

class TwitchVimeoAdapter(BaseAdapter):
    """
    Ingests technical live streams, conference talks, and creative coding videos from Twitch and Vimeo.
    """

    async def fetch_items(self, feed_config: Dict[str, Any], limit: int = 3) -> List[OmnichannelItem]:
        items: List[OmnichannelItem] = []
        platform = feed_config.get("platform", "video")
        url = feed_config.get("url")
        channel_name = feed_config.get("name", "Video Channel")

        if not url:
            return items

        try:
            # Vimeo RSS or general video feed
            if "vimeo.com" in url or platform == "vimeo":
                feed_url = url
                if not feed_url.endswith("/rss") and "channels" in feed_url:
                    feed_url = f"{feed_url.rstrip('/')}/videos/rss"

                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:limit]:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", "")
                    clean_desc = re.sub(r"<[^>]+>", " ", summary).strip()
                    v_id = entry.get("id") or link

                    items.append(OmnichannelItem(
                        id=f"vimeo_{re.sub(r'[^a-zA-Z0-9]', '_', str(v_id))[:40]}",
                        platform="vimeo",
                        source_name=channel_name,
                        title=title,
                        url=link,
                        author=channel_name,
                        published_at=datetime.now(timezone.utc),
                        content_text=f"Platform: Vimeo\nChannel: {channel_name}\nTitle: {title}\nURL: {link}\nOverview: {clean_desc}",
                        summary_hint=clean_desc[:150] if clean_desc else title,
                        category=feed_config.get("category", "tech_updates"),
                        tags=["Vimeo", channel_name, "TechTalk"]
                    ))

            elif "twitch.tv" in url or platform == "twitch":
                # Twitch channel metadata & recent VODs / info
                streamer = url.rstrip("/").split("/")[-1]
                items.append(OmnichannelItem(
                    id=f"twitch_{streamer}",
                    platform="twitch",
                    source_name=f"Twitch ({streamer})",
                    title=f"Live Coding & Tech Broadcast by {streamer}",
                    url=url,
                    author=streamer,
                    published_at=datetime.now(timezone.utc),
                    content_text=f"Platform: Twitch Live\nStreamer: {streamer}\nChannel URL: {url}\nFocus: Engineering, AI development, and live tech commentary.",
                    summary_hint=f"Twitch technical stream: {streamer}",
                    category=feed_config.get("category", "developer_discussion"),
                    tags=["Twitch", streamer, "LiveCoding"]
                ))

        except Exception as e:
            logger.error(f"Error fetching Twitch/Vimeo feed {url}: {e}")

        return items
