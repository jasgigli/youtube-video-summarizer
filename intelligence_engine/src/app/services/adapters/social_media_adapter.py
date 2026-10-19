from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from src.app.config import settings
from src.app.services.adapters.base_adapter import BaseAdapter, OmnichannelItem


class SocialMediaAdapter(BaseAdapter):
    """Fetches public company posts through the official X and LinkedIn APIs."""

    async def fetch_items(
        self,
        feed_config: Dict[str, Any],
        limit: int = 5
    ) -> List[OmnichannelItem]:
        feed_type = feed_config.get("type")
        if feed_type == "x_account":
            return await self._fetch_x_posts(feed_config, limit)
        if feed_type == "linkedin_company":
            return await self._fetch_linkedin_posts(feed_config, limit)
        raise ValueError(f"Unsupported social media feed type: {feed_type}")

    async def _fetch_x_posts(
        self,
        feed_config: Dict[str, Any],
        limit: int
    ) -> List[OmnichannelItem]:
        token = settings.X_BEARER_TOKEN
        handle = (feed_config.get("handle") or "").strip().lstrip("@")
        if not token:
            raise ValueError("X source requires X_BEARER_TOKEN.")
        if not handle:
            raise ValueError(f"X source '{feed_config.get('name')}' has no account handle.")

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            user_response = await client.get(
                f"https://api.x.com/2/users/by/username/{quote(handle)}",
                headers=headers
            )
            user_response.raise_for_status()
            user = user_response.json()["data"]

            posts_response = await client.get(
                f"https://api.x.com/2/users/{user['id']}/tweets",
                headers=headers,
                params={
                    "max_results": max(5, min(limit, 100)),
                    "exclude": "replies,retweets",
                    "tweet.fields": "created_at,public_metrics,entities,lang"
                }
            )
            posts_response.raise_for_status()
            posts = posts_response.json().get("data", [])

        items = []
        for post in posts:
            post_id = post.get("id")
            text = post.get("text", "").strip()
            if not post_id or not text:
                continue

            created_at = self._parse_datetime(post.get("created_at"))
            if created_at and self._is_too_old(created_at, feed_config):
                continue

            entities = post.get("entities") or {}
            expanded_urls = [
                entry.get("expanded_url")
                for entry in entities.get("urls", [])
                if entry.get("expanded_url")
            ]
            metrics = post.get("public_metrics") or {}
            items.append(OmnichannelItem(
                id=f"x_{post_id}",
                platform="twitter_x",
                source_name=feed_config.get("name", f"X — {handle}"),
                title=text[:180],
                url=f"https://x.com/{handle}/status/{post_id}",
                author=f"@{handle}",
                published_at=created_at,
                content_text=(
                    f"X post by @{handle}:\n{text}\n"
                    f"Referenced links: {', '.join(expanded_urls) or 'None'}"
                ),
                summary_hint=text[:400],
                category=feed_config.get("category", "Social Media — X"),
                engagement={
                    "likes": metrics.get("like_count", 0),
                    "reposts": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "quotes": metrics.get("quote_count", 0)
                },
                tags=["X", "SocialDiscussion", post.get("lang") or "unknown"]
            ))
            if len(items) >= limit:
                break
        return items

    async def _fetch_linkedin_posts(
        self,
        feed_config: Dict[str, Any],
        limit: int
    ) -> List[OmnichannelItem]:
        token = settings.LINKEDIN_ACCESS_TOKEN
        organization_id = str(feed_config.get("organization_id", "")).strip()
        if not token:
            raise ValueError("LinkedIn source requires LINKEDIN_ACCESS_TOKEN.")
        if not organization_id:
            raise ValueError(
                f"LinkedIn source '{feed_config.get('name')}' requires an organization_id."
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.linkedin.com/rest/posts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "LinkedIn-Version": settings.LINKEDIN_API_VERSION,
                    "X-Restli-Protocol-Version": "2.0.0"
                },
                params={
                    "q": "author",
                    "author": f"urn:li:organization:{organization_id}",
                    "count": limit,
                    "sortBy": "LAST_MODIFIED"
                }
            )
            response.raise_for_status()
            posts = response.json().get("elements", [])

        items = []
        for post in posts:
            commentary = post.get("commentary", "").strip()
            post_id = post.get("id")
            if not commentary or not post_id:
                continue

            timestamp_ms = post.get("publishedAt") or post.get("createdAt")
            published_at: Optional[datetime] = None
            if timestamp_ms is not None:
                try:
                    published_at = datetime.fromtimestamp(
                        int(timestamp_ms) / 1000,
                        tz=timezone.utc
                    )
                except (TypeError, ValueError, OSError):
                    published_at = None
            if published_at and self._is_too_old(published_at, feed_config):
                continue

            slug = feed_config.get("slug", "company")
            items.append(OmnichannelItem(
                id=f"linkedin_{post_id}",
                platform="linkedin",
                source_name=feed_config.get("name", f"LinkedIn — {slug}"),
                title=commentary[:180],
                url=f"https://www.linkedin.com/feed/update/{post_id}/",
                author=slug,
                published_at=published_at,
                content_text=f"LinkedIn organization post by {slug}:\n{commentary}",
                summary_hint=commentary[:400],
                category=feed_config.get("category", "Social Media — LinkedIn"),
                engagement={},
                tags=["LinkedIn", "CompanyAnnouncement"]
            ))
        return items[:limit]

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _is_too_old(published_at: datetime, feed_config: Dict[str, Any]) -> bool:
        max_age_days = feed_config.get("max_age_days")
        if max_age_days is None:
            return False
        cutoff = datetime.now(timezone.utc).timestamp() - int(max_age_days) * 86400
        return published_at.timestamp() < cutoff
