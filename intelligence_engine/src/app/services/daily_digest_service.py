import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.app.config import settings
from src.app.utils.logger import logger
from src.app.database import SessionLocal
from src.app.models.setting import Setting
from src.app.services.omnichannel_intelligence_service import OmnichannelIntelligenceService

DIGEST_PROMPT_TEMPLATE = """You are an executive intelligence analyst.
Below is a list of recent summaries from global technology news, official company and research feeds, open-source projects, and community discussions:

{intelligence_reports_block}

TASK:
1. Detect cross-source trends and duplicate or overlapping topics.
2. Group key developments into thematic clusters (e.g. "AI Runtime Wars", "Developer Tools", "Global Technology Policy").
3. For each thematic cluster:
   - Provide a bold 1-sentence headline.
   - List the sources discussing it and the key consensus or debate.
   - 2-3 concise bullet points summarizing the core takeaways.
4. Provide a 2-sentence executive brief at the very beginning.
Use only the supplied summaries. Do not infer facts, impact, or sentiment not present in them.

Return strictly raw valid JSON matching this schema:
{{
  "executive_brief": "2-sentence overall takeaway of today's tech developments.",
  "trending_topics": [
    {{
      "topic_title": "Theme name",
      "sources_involved": ["Source 1", "Source 2"],
      "key_takeaway": "1-2 sentence core message",
      "bullet_points": ["Bullet 1", "Bullet 2"]
    }}
  ],
  "notable_standalone_reports": [
    {{
      "title": "Report title",
      "sources": ["Source"],
      "one_liner": "Why it matters"
    }}
  ]
}}
"""

class DailyDigestService:
    """
    Compiles a daily cross-source brief from saved Markdown intelligence reports.
    """

    @classmethod
    def _read_recent_summaries(cls, max_days: int = 1) -> List[Dict[str, Any]]:
        """Reads individual intelligence reports generated in recent date folders."""
        summaries_dir = settings.SUMMARIES_PATH
        if not summaries_dir.exists():
            return []

        recent_files = []
        # Read the newest dated report folders first.
        for folder in sorted(summaries_dir.iterdir(), reverse=True):
            if folder.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", folder.name):
                for md_file in folder.glob("*.md"):
                    if md_file.name in ("DAILY_BRIEF.md", "README.md", "INDEX.md"):
                        continue
                    try:
                        content = md_file.read_text(encoding="utf-8")
                        title = md_file.stem
                        
                        # Extract channel / platforms
                        source = "Unknown Source"
                        m_chan = re.search(r"\*\*Channel:\*\*\s*(.+)", content)
                        if m_chan:
                            source = m_chan.group(1).strip()
                        else:
                            m_plat = re.search(r"\*\*Platforms Ingested:\*\*\s*(.+)", content)
                            if m_plat:
                                source = m_plat.group(1).strip()

                        # Extract One-Sentence Takeaway or Executive Summary
                        takeaway = ""
                        m_take = re.search(r"###? ⚡ Executive One-Sentence Takeaway\s*\n+>?\s*\*?\*?([^\n#\*]+)", content)
                        if not m_take:
                            m_take = re.search(r"###? 📌 One-Sentence Takeaway\s*\n+([^\n#]+)", content)
                        if not m_take:
                            m_take = re.search(r"## Executive Summary\s*\n+([^\n#]+)", content)
                        if m_take:
                            takeaway = m_take.group(1).strip()

                        # Extract Overview or highlights
                        overview = ""
                        m_over = re.search(r"### 🎯 Context & Overview\s*\n+([^\n#]+)", content)
                        if not m_over:
                            m_over = re.search(r"### 🔬 Feature/Release Details\s*\n+([^\n#]+)", content)
                        if m_over:
                            overview = m_over.group(1).strip()

                        recent_files.append({
                            "title": title,
                            "source": source,
                            "takeaway": takeaway or overview[:250],
                            "path": str(md_file)
                        })
                    except Exception as e:
                        logger.debug(f"Could not read {md_file.name}: {e}")

            if len(recent_files) >= 40:
                break

        return recent_files

    @classmethod
    async def compile_daily_brief(cls) -> Optional[Path]:
        """
        Gathers recent global reports and writes a cross-source DAILY_BRIEF.md.
        """
        summaries = cls._read_recent_summaries()
        if not summaries:
            logger.info("No summaries found to compile Daily Brief.")
            return None

        # Build prompt payload
        summary_lines = []
        for s in summaries:
            summary_lines.append(f"- **{s['title']}** (Sources: {s['source']}): {s['takeaway']}")

        payload_text = "\n".join(summary_lines)
        prompt = DIGEST_PROMPT_TEMPLATE.format(intelligence_reports_block=payload_text)

        db = SessionLocal()
        try:
            provider_setting = db.query(Setting).filter(Setting.key == "default_provider").first()
            provider = provider_setting.value if provider_setting else settings.DEFAULT_PROVIDER
            key_setting = db.query(Setting).filter(
                Setting.key == f"{provider}_api_key"
            ).first()
            api_key = key_setting.value if key_setting else None
        finally:
            db.close()

        analysis = await OmnichannelIntelligenceService._call_provider(
            prompt,
            provider,
            api_key
        )

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
            f"> ⏱️ **Compiled:** {time_str} | **Reports Analyzed:** {len(summaries)} across global sources",
            "",
            "## ⚡ Executive Summary",
            f"{analysis.get('executive_brief', 'Key updates across AI and software engineering.')}",
            "",
            "## 📈 Cross-Source Trends & Duplicate Topic Detection",
            ""
        ]

        for topic in analysis.get("trending_topics", []):
            sources_str = ", ".join(topic.get("sources_involved", []))
            md_lines.append(f"### 🔥 {topic.get('topic_title', 'Industry Trend')}")
            md_lines.append(f"- **Covered by Sources:** `{sources_str}`")
            md_lines.append(f"- **Consensus / Insight:** {topic.get('key_takeaway', '')}")
            for bullet in topic.get("bullet_points", []):
                md_lines.append(f"  - {bullet}")
            md_lines.append("")

        if analysis.get("notable_standalone_reports"):
            md_lines.append("## 🌟 Notable Standalone Highlights")
            for report in analysis.get("notable_standalone_reports", []):
                sources = ", ".join(report.get("sources", []))
                md_lines.append(f"- **{report.get('title', '')}** (`{sources}`): {report.get('one_liner', '')}")
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

        return daily_brief_path
