import json
import re
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from src.app.config import settings
from src.app.utils.logger import logger
from src.app.services.notification_service import NotificationService
from src.app.services.audio_podcast_service import AudioPodcastService
from src.app.services.git_sync_service import GitSyncService

DIGEST_PROMPT_TEMPLATE = """You are an executive intelligence analyst.
Below is a list of YouTube video summaries published by tech channels in the last 24 hours:

{video_summaries_block}

TASK:
1. Detect cross-channel trends, duplicate or overlapping topics covered by multiple creators.
2. Group the key developments into 3 to 5 high-impact thematic clusters (e.g. "AI Runtime Wars", "Next-Gen Agentic Tools", "Career & Tech Job Market Shifts").
3. For each thematic cluster:
   - Provide a bold 1-sentence headline.
   - List the channels discussing it and the key consensus or debate.
   - 2-3 concise bullet points summarizing the core takeaways.
4. Provide a 2-sentence "Executive Morning Brief" summary at the very beginning.

Return strictly raw valid JSON matching this schema:
{{
  "executive_brief": "2-sentence overall takeaway of today's tech developments.",
  "trending_topics": [
    {{
      "topic_title": "Theme name",
      "channels_involved": ["Channel 1", "Channel 2"],
      "key_takeaway": "1-2 sentence core message",
      "bullet_points": ["Bullet 1", "Bullet 2"]
    }}
  ],
  "notable_standalone_videos": [
    {{
      "title": "Video title",
      "channel": "Channel",
      "one_liner": "Why it matters"
    }}
  ]
}}
"""

class DailyDigestService:
    """
    Compiles daily intelligence briefs across all processed channels,
    detects cross-channel trends and duplicate topics, creates DAILY_BRIEF.md,
    and synthesizes an automated morning briefing audio podcast.
    """

    @classmethod
    def _read_recent_summaries(cls, max_days: int = 1) -> List[Dict[str, Any]]:
        """Reads markdown summary files generated in the recent folders."""
        summaries_dir = settings.SUMMARIES_PATH
        if not summaries_dir.exists():
            return []

        recent_files = []
        # Look into today's and yesterday's directory
        for folder in sorted(summaries_dir.iterdir(), reverse=True):
            if folder.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", folder.name):
                for md_file in folder.glob("*.md"):
                    if md_file.name in ("DAILY_BRIEF.md", "README.md", "INDEX.md"):
                        continue
                    try:
                        content = md_file.read_text(encoding="utf-8")
                        title = md_file.stem
                        
                        # Extract channel and category
                        channel = "Unknown Channel"
                        m_chan = re.search(r"\*\*Channel:\*\*\s*(.+)", content)
                        if m_chan:
                            channel = m_chan.group(1).strip()

                        # Extract One-Sentence Takeaway
                        takeaway = ""
                        m_take = re.search(r"### 📌 One-Sentence Takeaway\s*\n+([^\n#]+)", content)
                        if m_take:
                            takeaway = m_take.group(1).strip()

                        # Extract Overview
                        overview = ""
                        m_over = re.search(r"### 🎯 Context & Overview\s*\n+([^\n#]+)", content)
                        if m_over:
                            overview = m_over.group(1).strip()

                        recent_files.append({
                            "title": title,
                            "channel": channel,
                            "takeaway": takeaway or overview[:200],
                            "path": str(md_file)
                        })
                    except Exception as e:
                        logger.debug(f"Could not read {md_file.name}: {e}")

            if len(recent_files) >= 30:
                break

        return recent_files

    @classmethod
    async def compile_daily_brief(cls) -> Optional[Path]:
        """
        Gathers recent summaries, sends them to Gemini for cross-channel trend
        and duplicate detection, saves DAILY_BRIEF.md, and creates DAILY_BRIEF.mp3.
        """
        summaries = cls._read_recent_summaries()
        if not summaries:
            logger.info("No summaries found to compile Daily Brief.")
            return None

        # Build prompt payload
        summary_lines = []
        for s in summaries[:25]:
            summary_lines.append(f"- **{s['title']}** (Channel: {s['channel']}): {s['takeaway']}")

        payload_text = "\n".join(summary_lines)
        prompt = DIGEST_PROMPT_TEMPLATE.format(video_summaries_block=payload_text)

        key = settings.GEMINI_API_KEY
        if not key:
            logger.warning("GEMINI_API_KEY is not set. Skipping automated daily digest compilation.")
            return None

        analysis = None
        models_to_try = [settings.DEFAULT_MODEL_GEMINI, "gemini-flash-latest", "gemini-flash-lite-latest"]
        async with httpx.AsyncClient(timeout=60.0) as client:
            for model_candidate in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_candidate}:generateContent?key={key}"
                try:
                    resp = await client.post(
                        url,
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
                        analysis = json.loads(raw_json)
                        break
                    elif resp.status_code in (429, 503):
                        await asyncio.sleep(2)
                        continue
                except Exception as ex:
                    logger.debug(f"Model {model_candidate} digest generation error: {ex}")

        if not analysis:
            logger.warning("Could not generate daily digest from LLM.")
            return None

        # Format DAILY_BRIEF.md
        pkt_tz = ZoneInfo("Asia/Karachi")
        now_pkt = datetime.now(pkt_tz)
        date_str = now_pkt.strftime("%A, %d %b %Y")
        time_str = now_pkt.strftime("%I:%M %p PKT")

        md_lines = [
            f"# ☕ Daily Executive Tech Briefing — {date_str}",
            "",
            f"> ⏱️ **Compiled:** {time_str} | **Videos Analyzed:** {len(summaries)} across subscribed channels",
            "",
            "## ⚡ Executive Summary",
            f"{analysis.get('executive_brief', 'Key updates across AI and software engineering.')}",
            "",
            "## 📈 Cross-Channel Trends & Duplicate Topic Detection",
            ""
        ]

        for topic in analysis.get("trending_topics", []):
            channels_str = ", ".join(topic.get("channels_involved", []))
            md_lines.append(f"### 🔥 {topic.get('topic_title', 'Industry Trend')}")
            md_lines.append(f"- **Covered by Channels:** `{channels_str}`")
            md_lines.append(f"- **Consensus / Insight:** {topic.get('key_takeaway', '')}")
            for bullet in topic.get("bullet_points", []):
                md_lines.append(f"  - {bullet}")
            md_lines.append("")

        if analysis.get("notable_standalone_videos"):
            md_lines.append("## 🌟 Notable Standalone Highlights")
            for video in analysis.get("notable_standalone_videos", []):
                md_lines.append(f"- **{video.get('title', '')}** (`{video.get('channel', '')}`): {video.get('one_liner', '')}")
            md_lines.append("")

        briefing_content = "\n".join(md_lines)

        # Save strictly into the date folder: summaries/YYYY-MM-DD/DAILY_BRIEF.md
        today_str = now_pkt.strftime("%Y-%m-%d")
        daily_brief_path = settings.SUMMARIES_PATH / today_str / "DAILY_BRIEF.md"
        daily_brief_path.parent.mkdir(parents=True, exist_ok=True)
        daily_brief_path.write_text(briefing_content, encoding="utf-8")

        # Clean up any lingering DAILY_BRIEF in summaries root if it exists
        root_brief_path = settings.SUMMARIES_PATH / "DAILY_BRIEF.md"
        if root_brief_path.exists():
            root_brief_path.unlink()

        logger.info(f"Generated Daily Briefing: {daily_brief_path}")

        # Desktop Toast Notification
        NotificationService.notify_daily_digest(len(summaries))

        # Git Auto-Sync
        GitSyncService.sync_summaries()

        return daily_brief_path
