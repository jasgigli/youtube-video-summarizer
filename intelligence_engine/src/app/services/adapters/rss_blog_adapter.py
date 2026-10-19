import re
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import feedparser
from bs4 import BeautifulSoup
import httpx
from src.app.services.adapters.base_adapter import BaseAdapter, OmnichannelItem
from src.app.utils.logger import logger

class RSSBlogAdapter(BaseAdapter):
    """
    Ingests technical articles and official research announcements from:
    - Frontier AI labs (OpenAI, Google DeepMind, Anthropic, Meta AI)
    - Tech journalism (TechCrunch, The Verge, Ars Technica, Wired)
    - Engineering blogs (GitHub Blog, Cloudflare, Dev.to)
    """

    @staticmethod
    def clean_html(raw_html: str) -> str:
        """Strips HTML tags, scripts, and extra whitespace."""
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        text = soup.get_text(separator="\n")
        # Collapse multiple empty lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    @classmethod
    async def scrape_article(
        cls,
        client: httpx.AsyncClient,
        url: str,
        semaphore: asyncio.Semaphore
    ) -> str:
        if not url:
            return ""

        try:
            async with semaphore:
                response = await client.get(url)
            if response.status_code != 200:
                return ""

            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "header", "form"]):
                element.decompose()

            content_root = soup.find("article") or soup.find("main") or soup.body or soup
            paragraphs = [
                paragraph.get_text(" ", strip=True)
                for paragraph in content_root.find_all(["p", "h2", "h3"])
            ]
            article_text = "\n".join(text for text in paragraphs if len(text) > 40)
            if len(article_text) < 250:
                return ""
            return article_text[:6000]
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug(f"Could not scrape article {url}: {exc}")
            return ""

    async def fetch_web_page(
        self,
        feed_config: Dict[str, Any],
        limit: int = 5
    ) -> List[OmnichannelItem]:
        page_url = feed_config.get("url")
        if not page_url:
            raise ValueError(f"Web page source '{feed_config.get('name')}' has no URL.")

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TechIntelligenceBot/1.0)"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(page_url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header", "form"]):
            element.decompose()

        page_host = urlparse(page_url).netloc.lower()
        items: List[OmnichannelItem] = []
        seen_urls = set()
        for anchor in soup.find_all("a", href=True):
            if anchor.find_parent(["nav", "header", "footer"]):
                continue
            title = anchor.get_text(" ", strip=True)
            if len(title) < 24:
                continue

            article_url = urljoin(page_url, anchor["href"])
            parsed_article_url = urlparse(article_url)
            if parsed_article_url.scheme not in ("http", "https"):
                continue
            if parsed_article_url.netloc.lower() != page_host:
                continue
            if article_url in seen_urls or article_url.rstrip("/") == page_url.rstrip("/"):
                continue
            seen_urls.add(article_url)

            parent = anchor.find_parent("article") or anchor.find_parent("li") or anchor.parent
            description = parent.get_text(" ", strip=True) if parent else title
            time_tag = parent.find("time") if parent else None
            published_at = None
            if time_tag:
                date_text = time_tag.get("datetime") or time_tag.get_text(strip=True)
                try:
                    published_at = datetime.fromisoformat(
                        date_text.replace("Z", "+00:00")
                    )
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    published_at = None

            max_age_days = feed_config.get("max_age_days")
            if (
                published_at
                and max_age_days is not None
                and datetime.now(timezone.utc) - published_at > timedelta(days=int(max_age_days))
            ):
                continue

            item_id = re.sub(r"[^a-zA-Z0-9_]", "_", article_url)[-80:]
            items.append(OmnichannelItem(
                id=f"web_{item_id}",
                platform=feed_config.get("platform", "blog"),
                source_name=feed_config.get("name", "Technology News"),
                title=title[:240],
                url=article_url,
                published_at=published_at,
                content_text=(
                    f"Publication: {feed_config.get('name', 'Technology News')}\n"
                    f"Article title: {title}\nURL: {article_url}\n"
                    f"Listing excerpt: {description[:1500]}"
                ),
                summary_hint=description[:400],
                category=feed_config.get("category", "general_tech"),
                tags=[feed_config.get("name", "Technology News"), "OfficialWebPage"]
            ))
            if len(items) >= limit:
                break

        scrape_limit = max(0, int(feed_config.get("article_scrape_limit", 2)))
        candidates = items[:scrape_limit]
        if candidates:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                semaphore = asyncio.Semaphore(1)
                article_texts = await asyncio.gather(*[
                    self.scrape_article(client, item.url, semaphore)
                    for item in candidates
                ])
            for item, article_text in zip(candidates, article_texts):
                if article_text:
                    item.content_text += f"\n\nFull article text:\n{article_text}"
                    item.summary_hint = article_text[:400]

        if not items:
            logger.warning(
                f"Web page source '{feed_config.get('name')}' yielded no article links; "
                "the page may require JavaScript or restrict automated access."
            )
        return items

    async def fetch_items(self, feed_config: Dict[str, Any], limit: int = 5) -> List[OmnichannelItem]:
        items: List[OmnichannelItem] = []
        url = feed_config.get("url")
        feed_name = feed_config.get("name", "Tech Blog")
        platform = feed_config.get("platform", "blog")
        category = feed_config.get("category", "ai_frontier")

        if not url:
            return items

        try:
            # Fetch feed via httpx with proper user-agent
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 (OmnichannelTechIntelligence/2.0)"
            }
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"RSS Feed {feed_name} returned status {resp.status_code}")
                    return items
                feed_data = feedparser.parse(resp.text)

            max_age_days = feed_config.get("max_age_days", 14)
            for entry in feed_data.entries:
                if len(items) >= limit:
                    break
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                author = entry.get("author") or feed_name

                # Extract publish timestamp
                pub_dt = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                if pub_dt and max_age_days is not None:
                    age = datetime.now(timezone.utc) - pub_dt
                    if age > timedelta(days=max_age_days):
                        continue

                # Extract summary / content
                raw_content = ""
                if hasattr(entry, "content") and entry.content:
                    raw_content = entry.content[0].value
                elif hasattr(entry, "summary"):
                    raw_content = entry.summary

                clean_body = self.clean_html(raw_content)

                # Unique ID
                entry_id = entry.get("id") or link or title
                clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", entry_id)[:60]

                content_lines = [
                    f"Publication: {feed_name}",
                    f"Article Title: {title}",
                    f"URL: {link}",
                    f"Published: {pub_dt.strftime('%Y-%m-%d %H:%M UTC') if pub_dt else 'Recent'}",
                    f"\nArticle Overview & Core Text:\n{clean_body[:4000]}"
                ]

                items.append(OmnichannelItem(
                    id=f"{platform}_{clean_id}",
                    platform=platform,
                    source_name=feed_name,
                    title=title,
                    url=link,
                    author=author,
                    published_at=pub_dt,
                    content_text="\n".join(content_lines),
                    summary_hint=clean_body[:200] if clean_body else title,
                    category=category,
                    engagement={},
                    tags=[feed_name, platform, "Announcement"]
                ))

            scrape_limit = max(0, int(feed_config.get("article_scrape_limit", 3)))
            scrape_candidates = items[:scrape_limit]
            if scrape_candidates:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    semaphore = asyncio.Semaphore(1)
                    scraped_articles = await asyncio.gather(*[
                        self.scrape_article(client, item.url, semaphore)
                        for item in scrape_candidates
                    ])
                for item, article_text in zip(scrape_candidates, scraped_articles):
                    if article_text:
                        item.content_text += f"\n\nFull article text:\n{article_text}"
                        item.summary_hint = article_text[:400] or item.summary_hint

        except Exception as e:
            logger.error(f"Error parsing RSS feed for {feed_name} ({url}): {e}")

        return items
