import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import httpx
from src.app.services.adapters.base_adapter import BaseAdapter, OmnichannelItem
from src.app.utils.logger import logger

class HackerNewsAdapter(BaseAdapter):
    """
    Ingests top front-page stories from Hacker News.
    Retrieves high-signal technical discussions, upvotes, and developer reactions.
    """

    async def fetch_items(self, feed_config: Dict[str, Any], limit: int = 10) -> List[OmnichannelItem]:
        items: List[OmnichannelItem] = []
        url = feed_config.get("url", "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15")
        parsed_url = urlsplit(url)
        query = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
        query["hitsPerPage"] = str(limit)
        url = urlunsplit((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            urlencode(query),
            parsed_url.fragment
        ))

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"Hacker News Algolia returned {resp.status_code}")
                    return items

                data = resp.json()
                hits = data.get("hits", [])

                for hit in hits[:limit]:
                    story_id = hit.get("objectID")
                    title = hit.get("title", "").strip()
                    story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
                    author = hit.get("author", "hn_user")
                    points = hit.get("points", 0)
                    num_comments = hit.get("num_comments", 0)
                    created_at_str = hit.get("created_at")
                    pub_dt = None
                    if created_at_str:
                        try:
                            pub_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        except Exception:
                            pub_dt = datetime.now(timezone.utc)

                    # Fetch top 3-4 comments for stories with rich discussion
                    top_comments: List[Dict[str, str]] = []
                    if story_id and num_comments > 5:
                        try:
                            item_url = f"https://hn.algolia.com/api/v1/items/{story_id}"
                            item_resp = await client.get(item_url, timeout=10.0)
                            if item_resp.status_code == 200:
                                item_data = item_resp.json()
                                raw_children = item_data.get("children", [])
                                for c in raw_children[:4]:
                                    c_text = c.get("text", "")
                                    # Strip basic HTML tags from HN comment
                                    clean_text = re.sub(r"<[^>]+>", " ", c_text).strip()
                                    if clean_text:
                                        top_comments.append({
                                            "author": c.get("author", "hn_dev"),
                                            "text": clean_text[:350],
                                            "score": "top"
                                        })
                        except Exception as comment_err:
                            logger.debug(f"Could not fetch HN comments for {story_id}: {comment_err}")

                    content_lines = [
                        f"Hacker News Story: {title}",
                        f"Source URL: {story_url}",
                        f"HN Discussion: https://news.ycombinator.com/item?id={story_id}",
                        f"Points: {points} | Comments: {num_comments} | Author: {author}"
                    ]

                    if top_comments:
                        content_lines.append("\nHacker News Community Reaction & Technical Critique:")
                        for idx, c in enumerate(top_comments, 1):
                            content_lines.append(f"{idx}. ({c.get('author')}): {c.get('text')}")

                    items.append(OmnichannelItem(
                        id=f"hn_{story_id}",
                        platform="hackernews",
                        source_name="Hacker News",
                        title=title,
                        url=story_url,
                        author=author,
                        published_at=pub_dt,
                        content_text="\n\n".join(content_lines),
                        summary_hint=f"Hacker News discussion with {points} points and {num_comments} comments: {title}",
                        category=feed_config.get("category", "engineering_discussions"),
                        engagement={"upvotes": points, "comments_count": num_comments},
                        community_comments=top_comments,
                        tags=["HackerNews", "YC", "TechDiscussion"]
                    ))

            except Exception as e:
                logger.error(f"Error fetching Hacker News feed: {e}")

        return items
