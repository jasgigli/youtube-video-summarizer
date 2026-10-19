from datetime import datetime
from typing import List, Dict, Any, Optional
from src.app.services.adapters.base_adapter import BaseAdapter, OmnichannelItem
from src.app.services.youtube_service import YouTubeService
from src.app.services.transcript_service import TranscriptService
from src.app.utils.logger import logger

class YouTubeAdapter(BaseAdapter):
    """
    Ingests latest YouTube video releases and full spoken transcripts from subscribed channels.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.yt_service = YouTubeService(api_key=api_key)

    async def fetch_items(self, feed_config: Dict[str, Any], limit: int = 1) -> List[OmnichannelItem]:
        items: List[OmnichannelItem] = []
        channel_handle = feed_config.get("handle") or feed_config.get("url") or feed_config.get("name")
        if not channel_handle:
            return items

        try:
            channel_id = feed_config.get("channel_id")
            if channel_id:
                channel_info = {
                    "channel_id": channel_id,
                    "title": feed_config.get("name", channel_handle),
                    "custom_url": None
                }
            else:
                channel_info = await self.yt_service.resolve_channel(channel_handle)
            channel_id = channel_info.get("channel_id")
            channel_title = channel_info.get("title", channel_handle)

            videos = await self.yt_service.fetch_latest_videos(
                channel_id=channel_id,
                custom_url=channel_info.get("custom_url"),
                limit=limit
            )

            for v in videos[:limit]:
                video_id = v.get("video_id")
                title = v.get("title", "")
                video_url = v.get("video_url", f"https://www.youtube.com/watch?v={video_id}")
                pub_at = v.get("published_at")
                if isinstance(pub_at, str):
                    try:
                        pub_at = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                    except Exception:
                        pub_at = None

                # Fetch transcript
                transcript_text = ""
                t_res = await TranscriptService.fetch_transcript(video_id)
                if t_res.get("status") == "SUCCESS" and t_res.get("text"):
                    transcript_text = t_res["text"]
                else:
                    # Fallback to description
                    desc = v.get("description", "")
                    transcript_text = f"Spoken Transcript unavailable. Video Description:\n{desc}"

                content_parts = [
                    f"YouTube Channel: {channel_title}",
                    f"Video Title: {title}",
                    f"Video URL: {video_url}",
                    f"\nTranscript / Spoken Content:\n{transcript_text[:5000]}"
                ]

                items.append(OmnichannelItem(
                    id=f"youtube_{video_id}",
                    platform="youtube",
                    source_name=channel_title,
                    title=title,
                    url=video_url,
                    author=channel_title,
                    published_at=pub_at,
                    content_text="\n".join(content_parts),
                    summary_hint=title,
                    category=feed_config.get("category", "tech_updates"),
                    engagement={"views": v.get("view_count", 0)},
                    tags=[channel_title, "YouTube", "VideoTutorial"]
                ))

        except Exception as e:
            logger.error(f"Error fetching YouTube feed for {channel_handle}: {e}")

        return items
