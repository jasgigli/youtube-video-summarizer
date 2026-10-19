import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx
from src.app.config import settings
from src.app.utils.logger import logger
from src.app.services.clustering_service import TopicCluster
from src.app.services.markdown_storage_service import MarkdownStorageService

OMNICHANNEL_INTELLIGENCE_PROMPT = """You are an elite Technology & AI Intelligence Analyst.
Analyze the following multi-source data cluster gathered from across the tech ecosystem (YouTube, Reddit, Hacker News, GitHub, Tech Blogs, Frontier AI Labs):

==================== CLUSTER INGESTION DATA ====================
Topic: {canonical_title}
Platforms Involved: {platforms_str}
Sources: {sources_str}

Content & Discussion Signals:
{cluster_content}
================================================================

TASK:
Synthesize a deep, high-signal, executive intelligence briefing.
Use only facts present in the supplied source material. Do not invent features, benchmarks, adoption, impact, or community sentiment. Mark unknown details as unknown.
You must strictly extract:
1. Executive Summary: 2-3 concise sentences overview highlighting what happened and why it matters.
2. Feature/Release Details: Key technical specifications, benchmarks, parameters, or release points.
3. Industry Impact: How this affects developers, engineering teams, companies, or the broader market.
4. Community Reaction: Concrete insights and debate points only when discussion sources provide them.
5. Technical Takeaways: Applicable tools, APIs, frameworks, architectural shifts, or CLI commands.
6. Relevant Code / Tools / Links: Concrete repositories, documentation, or tools.

Return strictly raw valid JSON matching this schema:
{{
  "topic_title": "Clean, punchy, authoritative headline",
  "category": "ai_frontier | software_engineering | open_source | big_tech | startups_vc | hardware_chips",
  "category_display": "Human-friendly label with emoji (e.g. '🤖 Frontier AI', '🛠️ Open Source', '⚡ System Architecture')",
  "executive_summary": "Concise 2-3 sentence overview highlighting what happened and why it matters.",
  "feature_release_details": [
    "Specific technical specification or feature release point 1.",
    "Specific technical specification or feature release point 2.",
    "Specific technical specification or feature release point 3."
  ],
  "industry_impact": [
    "How this affects developers, companies, or end users point 1.",
    "How this affects developers, companies, or end users point 2."
  ],
  "community_reaction": [
    "Insight or debate point from Reddit/X/Hacker News discussion 1.",
    "Insight or debate point from Reddit/X/Hacker News discussion 2."
  ],
  "technical_takeaways": [
    "Applicable tools, APIs, frameworks, or architectural changes mentioned 1.",
    "Applicable tools, APIs, frameworks, or architectural changes mentioned 2."
  ],
  "actionable_resources": [
    "Link, repo, command, or implementation advice 1.",
    "Link, repo, command, or implementation advice 2."
  ],
  "key_entities": ["Entity1", "Entity2"],
  "sentiment": "bullish | critical | analytical | transformative | mixed"
}}
"""

class OmnichannelIntelligenceService:
    """
    Synthesizes multi-source intelligence reports from clustered topic threads
    across YouTube, Reddit, Hacker News, GitHub, and Frontier AI labs into
    comprehensive Markdown (.md) documents and social content suites.
    """

    @classmethod
    async def synthesize_cluster_report(
        cls,
        cluster: TopicCluster,
        provider: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends the clustered multi-platform data to LLM and returns structured analysis.
        """
        provider = (provider or settings.DEFAULT_PROVIDER).lower()
        if api_key is None:
            key_setting = {
                "gemini": settings.GEMINI_API_KEY,
                "openai": settings.OPENAI_API_KEY,
                "anthropic": settings.ANTHROPIC_API_KEY
            }.get(provider, "")
            api_key = key_setting

        cluster_content = cluster.get_combined_content()[:12000]
        prompt = OMNICHANNEL_INTELLIGENCE_PROMPT.format(
            canonical_title=cluster.canonical_title,
            platforms_str=", ".join([p.upper() for p in cluster.platforms]),
            sources_str=", ".join(cluster.sources),
            cluster_content=cluster_content
        )

        analysis = await cls._call_provider(prompt, provider, api_key)
        if not analysis or not analysis.get("topic_title") or not analysis.get("executive_summary"):
            if analysis:
                logger.warning("LLM returned an incomplete report; using source-only synthesis.")
            analysis = cls._build_source_only_synthesis(cluster)
        else:
            analysis["analysis_status"] = "llm_synthesized"
            analysis["key_entities"] = analysis.get("key_entities") or cluster.key_entities
        return analysis

    @classmethod
    async def _call_provider(
        cls,
        prompt: str,
        provider: str,
        api_key: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        if provider not in {"gemini", "openai", "anthropic", "ollama"}:
            logger.warning(f"Unsupported omnichannel synthesis provider: {provider}")
            return None
        if provider != "ollama" and not api_key:
            logger.warning(f"No API key configured for omnichannel provider '{provider}'.")
            return None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if provider == "gemini":
                    model = settings.DEFAULT_MODEL_GEMINI
                    response = await cls._post_with_retry(
                        client,
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        headers={"x-goog-api-key": api_key},
                        payload={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "temperature": 0.2,
                                "responseMimeType": "application/json"
                            }
                        }
                    )
                    response.raise_for_status()
                    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                elif provider == "openai":
                    response = await cls._post_with_retry(
                        client,
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        payload={
                            "model": settings.DEFAULT_MODEL_OPENAI,
                            "messages": [
                                {"role": "system", "content": "Return only factual JSON matching the requested schema."},
                                {"role": "user", "content": prompt}
                            ],
                            "response_format": {"type": "json_object"},
                            "temperature": 0.2
                        }
                    )
                    response.raise_for_status()
                    text = response.json()["choices"][0]["message"]["content"]
                elif provider == "anthropic":
                    response = await cls._post_with_retry(
                        client,
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01"
                        },
                        payload={
                            "model": settings.DEFAULT_MODEL_ANTHROPIC,
                            "max_tokens": 2500,
                            "system": "Return only factual JSON matching the requested schema.",
                            "messages": [{"role": "user", "content": prompt}]
                        }
                    )
                    response.raise_for_status()
                    text = response.json()["content"][0]["text"]
                else:
                    response = await cls._post_with_retry(
                        client,
                        f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                        headers={},
                        payload={
                            "model": settings.DEFAULT_MODEL_OLLAMA,
                            "messages": [{"role": "user", "content": prompt}],
                            "format": "json",
                            "stream": False,
                            "options": {"temperature": 0.2}
                        }
                    )
                    response.raise_for_status()
                    text = response.json()["message"]["content"]

            try:
                analysis = json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", text, flags=re.DOTALL)
                if not match:
                    raise
                analysis = json.loads(match.group(0))
            if not isinstance(analysis, dict):
                logger.warning(f"LLM provider '{provider}' returned non-object JSON.")
                return None
            return analysis
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.error(f"Omnichannel synthesis via '{provider}' failed: {exc}")
            return None

    @staticmethod
    async def _post_with_retry(
        client: httpx.AsyncClient,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any]
    ) -> httpx.Response:
        response = None
        for attempt in range(3):
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code not in (429, 503):
                return response
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        return response

    @classmethod
    def _build_source_only_synthesis(cls, cluster: TopicCluster) -> Dict[str, Any]:
        """Creates a clearly labeled report from collected source text without inferred claims."""
        top_item = cluster.items[0] if cluster.items else None
        title = cluster.canonical_title
        source_points = []
        community_points = []
        for item in cluster.items:
            excerpt = (item.summary_hint or item.content_text or item.title).strip()
            if excerpt and excerpt not in source_points:
                source_points.append(f"{item.source_name}: {excerpt[:350]}")
            for c in item.community_comments[:2]:
                comment = c.get("text", "").strip()
                if comment:
                    community_points.append(
                        f"{item.platform.capitalize()} ({c.get('author', 'user')}): {comment[:250]}"
                    )

        if not community_points:
            community_points = ["No discussion comments were collected for this topic."]

        return {
            "topic_title": title,
            "category": cluster.primary_category,
            "category_display": f"🌐 {cluster.primary_category.replace('_', ' ').title()}",
            "executive_summary": (
                f"{title}. Source-only report based on {len(cluster.items)} collected item(s) "
                f"from {len(cluster.sources)} source(s); AI synthesis was unavailable."
            ),
            "feature_release_details": source_points[:8] or ["No source excerpt was collected."],
            "industry_impact": [
                "Not assessed: the collected source material does not support an impact conclusion."
            ],
            "community_reaction": community_points[:3],
            "technical_takeaways": source_points[:5] or ["No technical details were collected."],
            "actionable_resources": [
                f"Primary source URL: {top_item.url}"
                for top_item in cluster.items
                if top_item.url
            ],
            "key_entities": cluster.key_entities or ["AI", "Software Engineering"],
            "sentiment": "analytical",
            "analysis_status": "source_only"
        }

    @classmethod
    def save_omnichannel_markdown(
        cls,
        cluster: TopicCluster,
        analysis: Dict[str, Any]
    ) -> Path:
        """
        Formats and saves the comprehensive Markdown (.md) document matching the user's exact requirements.
        """
        base_dir = settings.SUMMARIES_PATH
        today_str = datetime.now().strftime("%Y-%m-%d")
        date_folder = base_dir / today_str
        date_folder.mkdir(parents=True, exist_ok=True)

        clean_title = MarkdownStorageService.sanitize_filename(analysis.get("topic_title", cluster.canonical_title))
        if not clean_title:
            clean_title = f"topic_{cluster.cluster_id}"
        file_path = date_folder / f"{clean_title}.md"
        if file_path.exists():
            existing_content = file_path.read_text(encoding="utf-8", errors="replace")
            marker = f"<!-- cluster-id: {cluster.cluster_id} -->"
            if marker not in existing_content:
                file_path = date_folder / f"{clean_title}-{cluster.cluster_id[-8:]}.md"

        pkt_time_str = MarkdownStorageService.format_pkt_datetime(datetime.now(timezone.utc))
        platforms_badges = " ".join([f"`{p.upper()}`" for p in sorted(cluster.platforms)])
        sources_list = ", ".join(sorted(cluster.sources))
        entities_list = ", ".join(analysis.get("key_entities", cluster.key_entities) or ["Tech Ecosystem"])

        # Format source links list
        source_links = []
        for itm in cluster.items:
            source_links.append(f"[{itm.source_name}: {itm.title[:45]}]({itm.url})")
        sources_md = " | ".join(source_links) if source_links else "Aggregated Feeds"

        md_lines = [
            f"<!-- cluster-id: {cluster.cluster_id} -->",
            "",
            f"# {analysis.get('topic_title', cluster.canonical_title)}",
            "",
            f"> 🌐 **Platforms Ingested:** {platforms_badges}  ",
            f"> 📡 **Sources:** {sources_list}  ",
            f"> 🏢 **Key Entities:** {entities_list}  ",
            f"> ⏱️ **Timestamp:** {pkt_time_str}  ",
            f"> 🔗 **Primary References:** {sources_md}  ",
            "",
            "---",
            "",
            "## Executive Summary",
            f"{analysis.get('executive_summary', '')}",
        ]

        if analysis.get("analysis_status") == "source_only":
            md_lines.extend([
                "",
                "> **Source-only report:** AI synthesis was unavailable. Claims below are limited to collected source material; impact and interpretation have not been independently synthesized.",
            ])

        source_only = analysis.get("analysis_status") == "source_only"
        md_lines.extend([
            "",
            "## Key Highlights & Breakdowns",
            "",
            "### 🔎 Collected Source Details" if source_only else "### 🔬 Feature/Release Details",
        ])
        for pt in analysis.get("feature_release_details", []):
            label = "Source excerpt" if source_only else "Technical Spec"
            md_lines.append(f"* **{label}:** {pt}")

        md_lines.extend([
            "",
            "### 🏢 Industry Impact",
        ])
        for pt in analysis.get("industry_impact", []):
            md_lines.append(f"* **Ecosystem Shift:** {pt}")

        md_lines.extend([
            "",
            "### 💬 Community Reaction",
        ])
        for pt in analysis.get("community_reaction", []):
            md_lines.append(f"* **Developer Sentiment (Reddit/X/HN):** {pt}")

        md_lines.extend([
            "",
            "## Source Excerpts" if source_only else "## Technical Takeaways",
        ])
        for pt in analysis.get("technical_takeaways", []):
            md_lines.append(f"* {pt}")

        if analysis.get("actionable_resources"):
            md_lines.extend([
                "",
                "## Actionable Resources & References",
            ])
            for res in analysis.get("actionable_resources", []):
                md_lines.append(f"* {res}")

        md_lines.append("")
        content = "\n".join(md_lines)
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Saved Omnichannel Markdown Document: {file_path}")

        # Update Master Index (summaries/INDEX.md)
        try:
            MarkdownStorageService._update_master_index(
                base_dir=base_dir,
                date_str=today_str,
                cat_display=analysis.get("category_display", "🌐 Tech Intel"),
                channel_name=f"[{'+'.join(cluster.platforms)}] {sources_list[:30]}",
                video_title=analysis.get("topic_title", cluster.canonical_title),
                video_url=cluster.items[0].url if cluster.items else "https://github.com/trending",
                rel_file_path=f"./{today_str}/{file_path.name}",
                one_sentence=analysis.get("executive_summary", "")[:120]
            )
        except Exception as idx_err:
            logger.error(f"Could not update summary index for {file_path.name}: {idx_err}")

        return file_path
