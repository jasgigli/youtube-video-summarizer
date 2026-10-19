import re
import json
import httpx
import feedparser
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.app.config import settings
from src.app.utils.logger import logger

class YouTubeService:
    """
    Resilient YouTube service supporting:
    1. Zero-key channel page scraping (extracts videos & metadata directly from YouTube)
    2. Zero-key RSS feed fallback
    3. Official YouTube Data API v3 (when configured)
    Prevents pipeline failures due to rate limits (HTTP 403/429) or missing keys.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.YOUTUBE_API_KEY
        self.headers = {"User-Agent": self.USER_AGENT}

    async def resolve_channel(self, identifier: str) -> Dict[str, Any]:
        """
        Resolves a user-provided identifier (URL, @handle, or channel ID)
        into normalized channel metadata: channel_id, title, thumbnail_url, custom_url.
        """
        identifier = identifier.strip()

        # Check if already a raw channel ID (UC...)
        if re.match(r"^UC[\w\-]{21,23}$", identifier):
            return await self._fetch_channel_metadata(identifier)

        # Normalize handle or URL
        clean_handle = identifier
        if "youtube.com" in identifier or "youtu.be" in identifier:
            match_handle = re.search(r"@([a-zA-Z0-9_\-\.]+)", identifier)
            if match_handle:
                clean_handle = f"@{match_handle.group(1)}"
            else:
                match_uc = re.search(r"/channel/(UC[\w\-]{21,23})", identifier)
                if match_uc:
                    return await self._fetch_channel_metadata(match_uc.group(1))
        elif not clean_handle.startswith("@") and not clean_handle.startswith("UC"):
            clean_handle = f"@{clean_handle}"

        # Resolve via public YouTube channel page HTML
        target_url = f"https://www.youtube.com/{clean_handle}"
        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=12.0) as client:
                resp = await client.get(target_url)
                if resp.status_code == 200:
                    html = resp.text

                    # Extract channel ID using multiple pattern fallbacks
                    channel_id_match = (
                        re.search(r'"browseId":"(UC[\w\-]{21,23})"', html) or
                        re.search(r'<meta itemprop="identifier" content="(UC[\w\-]{21,23})">', html) or
                        re.search(r'href="https://www.youtube.com/channel/(UC[\w\-]{21,23})"', html) or
                        re.search(r'"channelId":"(UC[\w\-]{21,23})"', html)
                    )
                    
                    if channel_id_match:
                        channel_id = channel_id_match.group(1)
                    else:
                        raise ValueError(f"Could not find YouTube channel ID for '{identifier}'")

                    # Extract title
                    title_match = (
                        re.search(r'<meta property="og:title" content="([^"]+)">', html) or
                        re.search(r'"title":"([^"]+)"', html)
                    )
                    title = title_match.group(1) if title_match else clean_handle

                    # Extract thumbnail
                    thumb_match = (
                        re.search(r'<meta property="og:image" content="([^"]+)">', html) or
                        re.search(r'"avatar":{"thumbnails":\[{"url":"([^"]+)"', html)
                    )
                    thumbnail = thumb_match.group(1) if thumb_match else ""

                    # Extract description
                    desc_match = re.search(r'<meta property="og:description" content="([^"]+)">', html)
                    description = desc_match.group(1) if desc_match else ""

                    return {
                        "channel_id": channel_id,
                        "title": title,
                        "custom_url": clean_handle if clean_handle.startswith("@") else None,
                        "description": description,
                        "thumbnail_url": thumbnail,
                        "subscriber_count": 0
                    }
        except Exception as e:
            logger.warning(f"Direct channel page resolution encountered: {e}")

        # If API key is available, attempt resolution via YouTube Data API
        if self.api_key:
            return await self._resolve_channel_via_api(clean_handle)

        raise ValueError(f"Unable to resolve YouTube channel '{identifier}'. Please verify the URL or handle.")

    async def _fetch_channel_metadata(self, channel_id: str) -> Dict[str, Any]:
        """Fetches metadata for a confirmed channel ID."""
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
                resp = await client.get(rss_url)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    feed_title = feed.feed.get("title", f"Channel {channel_id}")
                    feed_author = feed.feed.get("author", feed_title)
                    return {
                        "channel_id": channel_id,
                        "title": feed_author or feed_title,
                        "custom_url": None,
                        "description": feed.feed.get("summary", ""),
                        "thumbnail_url": f"https://yt3.googleusercontent.com/ytc/default",
                        "subscriber_count": 0
                    }
        except Exception as e:
            logger.error(f"Error reading channel RSS: {e}")

        return {
            "channel_id": channel_id,
            "title": f"YouTube Channel ({channel_id})",
            "custom_url": None,
            "description": "",
            "thumbnail_url": "",
            "subscriber_count": 0
        }

    async def _resolve_channel_via_api(self, handle: str) -> Dict[str, Any]:
        """Resolves handle via official YouTube Data API v3."""
        clean_handle = handle.lstrip("@")
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "part": "snippet,statistics",
            "forHandle": clean_handle,
            "key": self.api_key
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    item = items[0]
                    snippet = item.get("snippet", {})
                    stats = item.get("statistics", {})
                    return {
                        "channel_id": item.get("id"),
                        "title": snippet.get("title"),
                        "custom_url": snippet.get("customUrl", f"@{clean_handle}"),
                        "description": snippet.get("description", ""),
                        "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                        "subscriber_count": int(stats.get("subscriberCount", 0))
                    }
        raise ValueError(f"Could not resolve channel handle @{clean_handle} via YouTube API")

    async def fetch_latest_videos(
        self,
        channel_id: str,
        custom_url: Optional[str] = None,
        limit: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Fetches latest videos for a channel using a resilient multi-stage strategy:
        Stage 1: Channel Videos page HTML ingestion (lockupViewModel & videoRenderer). Zero API quota.
        Stage 2: Public RSS feed.
        Stage 3: Official YouTube Data API v3.
        """
        # 1. Primary Zero-Quota Engine: Direct channel videos tab scraping
        target_path = custom_url if custom_url else f"channel/{channel_id}"
        videos_url = f"https://www.youtube.com/{target_path}/videos"
        
        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=12.0) as client:
                resp = await client.get(videos_url)
                if resp.status_code == 200:
                    videos = self._parse_videos_from_html(resp.text, limit)
                    if videos:
                        logger.info(f"Discovered {len(videos)} videos directly via channel page for {channel_id}")
                        return videos
        except Exception as e:
            logger.warning(f"Channel page scraping fallback notice: {e}")

        # 2. Secondary Zero-Quota Engine: Public RSS feed
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
                resp = await client.get(rss_url)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    videos = []
                    for entry in feed.entries[:limit]:
                        video_id = entry.get("yt_videoid")
                        if not video_id:
                            match = re.search(r"v=([a-zA-Z0-9_\-]{11})", entry.get("link", ""))
                            if match:
                                video_id = match.group(1)
                        if not video_id:
                            continue

                        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                        pub_date = datetime.utcnow()
                        if "published_parsed" in entry and entry.published_parsed:
                            try:
                                pub_date = datetime(*entry.published_parsed[:6])
                            except Exception:
                                pass

                        videos.append({
                            "video_id": video_id,
                            "title": entry.get("title", "Untitled Video"),
                            "description": entry.get("summary", ""),
                            "published_at": pub_date,
                            "thumbnail_url": thumbnail,
                            "video_url": f"https://www.youtube.com/watch?v={video_id}",
                            "duration_seconds": 0
                        })
                    if videos:
                        logger.info(f"Retrieved {len(videos)} videos via RSS for {channel_id}")
                        return videos
        except Exception as e:
            logger.warning(f"RSS fetch notice: {e}")

        # 3. Official API Engine (if key provided)
        if self.api_key:
            return await self._fetch_videos_via_api(channel_id, limit)

        return []

    def _parse_videos_from_html(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parses video entries from ytInitialData lockupViewModel or videoRenderer."""
        match = re.search(r'var ytInitialData = ({.*?});</script>', html)
        if not match:
            match = re.search(r'window\["ytInitialData"\] = ({.*?});', html)
        if not match:
            return []

        try:
            data = json.loads(match.group(1))
        except Exception:
            return []

        videos = []
        seen_ids = set()

        tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
        for t in tabs:
            content = t.get('tabRenderer', {}).get('content', {})
            if 'richGridRenderer' in content:
                items = content['richGridRenderer'].get('contents', [])
                for item in items:
                    # New YouTube schema: lockupViewModel
                    vm = item.get('richItemRenderer', {}).get('content', {}).get('lockupViewModel')
                    if vm:
                        content_type = vm.get('contentType', '')
                        if settings.FILTER_OUT_SHORTS and 'SHORTS' in content_type:
                            continue

                        vid = vm.get('contentId')
                        meta = vm.get('metadata', {}).get('lockupMetadataViewModel', {})
                        title = meta.get('title', {}).get('content', '')

                        # Check title keywords for Shorts and Live streams
                        title_lower = (title or '').lower()
                        if settings.FILTER_OUT_SHORTS and ('#shorts' in title_lower or '#short' in title_lower):
                            continue
                        if settings.FILTER_OUT_LIVE_STREAMS and ('🔴' in title or 'live stream' in title_lower or '[live]' in title_lower):
                            continue

                        if vid and vid not in seen_ids and len(vid) == 11:
                            seen_ids.add(vid)
                            videos.append({
                                "video_id": vid,
                                "title": title or f"Video {vid}",
                                "description": "",
                                "published_at": datetime.utcnow(),
                                "thumbnail_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                                "video_url": f"https://www.youtube.com/watch?v={vid}",
                                "duration_seconds": 0
                            })
                            if len(videos) >= limit:
                                return videos

                    # Classic YouTube schema: videoRenderer
                    vr = item.get('richItemRenderer', {}).get('content', {}).get('videoRenderer')
                    if vr:
                        # Check badges for live stream
                        badges = [b.get('metadataBadgeRenderer', {}).get('style', '') for b in vr.get('badges', [])]
                        if settings.FILTER_OUT_LIVE_STREAMS and any('LIVE' in b for b in badges):
                            continue

                        vid = vr.get('videoId')
                        title = vr.get('title', {}).get('runs', [{}])[0].get('text', '')
                        title_lower = (title or '').lower()
                        if settings.FILTER_OUT_SHORTS and ('#shorts' in title_lower or '#short' in title_lower):
                            continue
                        if settings.FILTER_OUT_LIVE_STREAMS and ('🔴' in title or 'live stream' in title_lower):
                            continue

                        if vid and vid not in seen_ids:
                            seen_ids.add(vid)
                            videos.append({
                                "video_id": vid,
                                "title": title or f"Video {vid}",
                                "description": "",
                                "published_at": datetime.utcnow(),
                                "thumbnail_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                                "video_url": f"https://www.youtube.com/watch?v={vid}",
                                "duration_seconds": 0
                            })
                            if len(videos) >= limit:
                                return videos

        return videos

    async def _fetch_videos_via_api(self, channel_id: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Fallback to official YouTube Data API v3."""
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "maxResults": min(limit, 25),
            "order": "date",
            "type": "video",
            "key": self.api_key
        }
        videos = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("items", []):
                        vid = item.get("id", {}).get("videoId")
                        snippet = item.get("snippet", {})
                        if not vid:
                            continue
                        
                        pub_time = datetime.utcnow()
                        if "publishedAt" in snippet:
                            try:
                                pub_time = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
                            except Exception:
                                pass

                        videos.append({
                            "video_id": vid,
                            "title": snippet.get("title", ""),
                            "description": snippet.get("description", ""),
                            "published_at": pub_time,
                            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                            "video_url": f"https://www.youtube.com/watch?v={vid}",
                            "duration_seconds": 0
                        })
        except Exception as e:
            logger.error(f"Error fetching videos via API: {e}")

        return videos
