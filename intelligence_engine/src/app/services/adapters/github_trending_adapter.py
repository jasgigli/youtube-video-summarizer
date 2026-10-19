import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from src.app.services.adapters.base_adapter import BaseAdapter, OmnichannelItem
from src.app.utils.logger import logger

class GitHubTrendingAdapter(BaseAdapter):
    """
    Ingests trending GitHub repositories across AI, machine learning, and software engineering.
    Extracts stars, description, primary language, and developer utility.
    """

    async def fetch_items(self, feed_config: Dict[str, Any], limit: int = 6) -> List[OmnichannelItem]:
        items: List[OmnichannelItem] = []
        url = feed_config.get("url", "https://github.com/trending?since=daily")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    repo_articles = soup.find_all("article", class_="Box-row")

                    for article in repo_articles[:limit]:
                        h2 = article.find("h2")
                        if not h2:
                            continue
                        a_tag = h2.find("a")
                        if not a_tag:
                            continue

                        repo_path = a_tag.get("href", "").strip().lstrip("/")
                        repo_title = re.sub(r"\s+", "", repo_path)
                        repo_url = f"https://github.com/{repo_path}"

                        desc_p = article.find("p")
                        description = desc_p.text.strip() if desc_p else "No description provided."

                        # Extract language
                        lang_span = article.find("span", itemprop="programmingLanguage")
                        language = lang_span.text.strip() if lang_span else "General"

                        # Extract stars
                        stars_a = article.find("a", href=re.compile(r"/stargazers$"))
                        stars_text = stars_a.text.strip() if stars_a else "0"

                        # Today stars
                        today_span = article.find("span", class_="d-inline-block float-sm-right")
                        today_stars = today_span.text.strip() if today_span else ""

                        content_block = (
                            f"GitHub Repository: {repo_title}\n"
                            f"URL: {repo_url}\n"
                            f"Language: {language}\n"
                            f"Stars: {stars_text} ({today_stars})\n\n"
                            f"Overview & Core Utility:\n{description}"
                        )

                        items.append(OmnichannelItem(
                            id=f"github_{repo_path.replace('/', '_')}",
                            platform="github",
                            source_name="GitHub Trending",
                            title=f"{repo_title}: {description[:70]}",
                            url=repo_url,
                            author=repo_path.split("/")[0] if "/" in repo_path else "GitHub",
                            published_at=datetime.now(timezone.utc),
                            content_text=content_block,
                            summary_hint=f"{repo_title} ({language}) - {description}",
                            category="open_source",
                            engagement={"stars": stars_text, "today_stars": today_stars},
                            tags=["GitHub", "OpenSource", language, "TrendingRepo"]
                        ))

            except Exception as e:
                logger.error(f"Error scraping GitHub trending: {e}")

        # Fallback to GitHub Search API if scraping was rate limited or empty
        if not items:
            try:
                api_url = (
                    "https://api.github.com/search/repositories"
                    f"?q=stars:>500+pushed:>2024-01-01&sort=updated&order=desc&per_page={limit}"
                )
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(api_url, headers={"User-Agent": "OmnichannelTechIntelligence"})
                    if resp.status_code == 200:
                        data = resp.json()
                        for repo in data.get("items", [])[:limit]:
                            full_name = repo.get("full_name")
                            items.append(OmnichannelItem(
                                id=f"github_{full_name.replace('/', '_')}",
                                platform="github",
                                source_name="GitHub Trending",
                                title=f"{full_name}: {repo.get('description', '')[:70]}",
                                url=repo.get("html_url"),
                                author=repo.get("owner", {}).get("login"),
                                published_at=datetime.now(timezone.utc),
                                content_text=f"Repo: {full_name}\nURL: {repo.get('html_url')}\nStars: {repo.get('stargazers_count')}\n{repo.get('description', '')}",
                                summary_hint=repo.get("description", ""),
                                category="open_source",
                                engagement={"stars": repo.get("stargazers_count", 0)},
                                tags=["GitHub", "OpenSource", repo.get("language") or "Code"]
                            ))
            except Exception as api_err:
                logger.debug(f"GitHub fallback API notice: {api_err}")

        return items
