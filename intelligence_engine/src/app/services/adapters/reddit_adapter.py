import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
import feedparser
from src.app.services.adapters.base_adapter import BaseAdapter, OmnichannelItem
from src.app.utils.logger import logger

REDDIT_USER_AGENT = "python:omnichannel.tech.intelligence:v2.0 (by /u/techdigestbot)"

class RedditAdapter(BaseAdapter):
    """
    Ingests top tech and AI discussions from Reddit communities (e.g. r/LocalLLaMA, r/MachineLearning).
    Features automatic zero-fail fallback to Google News Reddit Syndication when Reddit rate limits anonymous IP.
    """

    async def fetch_items(self, feed_config: Dict[str, Any], limit: int = 5) -> List[OmnichannelItem]:
        items: List[OmnichannelItem] = []
        subreddit = feed_config.get("subreddit")
        if not subreddit and "reddit.com/r/" in feed_config.get("url", ""):
            m = re.search(r"reddit\.com/r/([^/?]+)", feed_config["url"])
            if m:
                subreddit = m.group(1)

        subreddit = subreddit or "LocalLLaMA"
        direct_url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        headers = {"User-Agent": REDDIT_USER_AGENT}

        # 1. Attempt direct Reddit JSON
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(direct_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    children = data.get("data", {}).get("children", [])
                    for child in children[:limit]:
                        pdata = child.get("data", {})
                        if pdata.get("stickied", False):
                            continue
                        post_id = pdata.get("id", "")
                        title = pdata.get("title", "").strip()
                        selftext = pdata.get("selftext", "").strip()
                        author = pdata.get("author", "anonymous")
                        score = pdata.get("score", 0)
                        num_comments = pdata.get("num_comments", 0)
                        permalink = pdata.get("permalink", "")
                        post_url = f"https://www.reddit.com{permalink}" if permalink else pdata.get("url", "")
                        created_utc = pdata.get("created_utc")
                        try:
                            published_at = datetime.fromtimestamp(float(created_utc), timezone.utc)
                        except (TypeError, ValueError, OSError):
                            published_at = None

                        items.append(OmnichannelItem(
                            id=f"reddit_{post_id}",
                            platform="reddit",
                            source_name=feed_config.get("name", f"Reddit r/{subreddit}"),
                            title=title,
                            url=post_url,
                            author=f"u/{author}",
                            published_at=published_at,
                            content_text=f"Reddit Post: {title}\nSubreddit: r/{subreddit}\nAuthor: u/{author}\nUpvotes: {score} | Comments: {num_comments}\n\nContent:\n{selftext}",
                            summary_hint=selftext[:200] if selftext else title,
                            category=feed_config.get("category", "open_source"),
                            engagement={"upvotes": score, "comments_count": num_comments},
                            tags=[f"r/{subreddit}", "Reddit", "DeveloperDiscussion"]
                        ))
                    if items:
                        return items
        except Exception as e:
            logger.debug(f"Direct Reddit JSON access limited: {e}")

        # 2. Zero-fail Google News Reddit Syndication Fallback
        try:
            fallback_rss = f"https://news.google.com/rss/search?q=site:reddit.com/r/{subreddit}+when:3d"
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(fallback_rss, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    for entry in feed.entries[:limit]:
                        raw_title = entry.get("title", "")
                        # Clean " - Reddit" suffix
                        clean_title = re.sub(r"\s*-\s*Reddit$", "", raw_title).strip()
                        link = entry.get("link", "")
                        clean_body = re.sub(r"<[^>]+>", " ", entry.get("summary", "")).strip()
                        published_at = None
                        if entry.get("published_parsed"):
                            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                        clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", clean_title)[:40]
                        items.append(OmnichannelItem(
                            id=f"reddit_rss_{clean_id}",
                            platform="reddit",
                            source_name=feed_config.get("name", f"Reddit r/{subreddit}"),
                            title=clean_title,
                            url=link,
                            author=f"r/{subreddit}",
                            published_at=published_at,
                            content_text=f"Community Discussion on r/{subreddit}:\nTitle: {clean_title}\nSource: {link}\nContext:\n{clean_body}",
                            summary_hint=clean_body[:200] if clean_body else clean_title,
                            category=feed_config.get("category", "open_source"),
                            engagement={"upvotes": "hot", "comments_count": "active"},
                            tags=[f"r/{subreddit}", "Reddit", "CommunityDiscussion"]
                        ))
        except Exception as fallback_err:
            logger.error(f"Error fetching Reddit fallback feed for r/{subreddit}: {fallback_err}")

        return items
