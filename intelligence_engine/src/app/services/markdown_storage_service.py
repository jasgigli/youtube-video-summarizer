import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from src.app.config import settings
from src.app.utils.logger import logger

class MarkdownStorageService:
    """
    Dedicated storage engine for saving concise, category-adaptive YouTube summaries
    as readable Markdown (.md) documents and maintaining a master index table.
    """

    @classmethod
    def sanitize_filename(cls, text: str) -> str:
        """Removes or replaces characters not permitted in Windows file systems."""
        # Replace invalid Windows chars : \ / * ? " < > |
        cleaned = re.sub(r'[\\/*?:"<>|]', "", text)
        # Strip consecutive dots to avoid Win32 path normalization issues
        cleaned = re.sub(r'\.{2,}', '', cleaned)
        cleaned = re.sub(r'\s+', " ", cleaned).strip().strip('. ')
        # Cap length to avoid MAX_PATH issues while keeping full title readable
        return cleaned[:100]

    @classmethod
    def format_pkt_datetime(cls, dt_val: Optional[Any] = None) -> str:
        """Formats datetime into human-friendly Asia/Karachi (PKT) timestamp."""
        try:
            from zoneinfo import ZoneInfo
            pkt_tz = ZoneInfo("Asia/Karachi")
            if not dt_val:
                return datetime.now(pkt_tz).strftime("%A, %d %b %Y (%I:%M %p PKT)")
            
            if isinstance(dt_val, str):
                dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
            elif isinstance(dt_val, datetime):
                dt = dt_val
            else:
                return datetime.now(pkt_tz).strftime("%A, %d %b %Y (%I:%M %p PKT)")

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            pkt_time = dt.astimezone(pkt_tz)
            return pkt_time.strftime("%A, %d %b %Y (%I:%M %p PKT)")
        except Exception:
            return datetime.now().strftime("%A, %d %b %Y (%I:%M %p PKT)")

    @classmethod
    def save_summary_markdown(
        cls,
        video_title: str,
        channel_name: str,
        video_url: str,
        video_id: str,
        published_at: Optional[Any],
        summary_data: Dict[str, Any]
    ) -> Path:
        """
        Generates and saves a polished Markdown file for the video summary,
        named ONLY with the video title, with minimal metadata and without tags.
        """
        base_dir = settings.SUMMARIES_PATH
        base_dir.mkdir(parents=True, exist_ok=True)

        # 1. Date folder: summaries/YYYY-MM-DD
        today_str = datetime.now().strftime("%Y-%m-%d")
        date_folder = base_dir / today_str
        date_folder.mkdir(parents=True, exist_ok=True)

        # 2. File name format: ONLY the video title
        clean_title = cls.sanitize_filename(video_title)
        if not clean_title:
            clean_title = f"video_{video_id}"
        filename = f"{clean_title}.md"
        file_path = date_folder / filename

        # 3. Format Markdown Document
        gen_date_str = cls.format_pkt_datetime(datetime.now(timezone.utc))

        one_sentence = summary_data.get("one_sentence_takeaway", "No summary takeaway available.")
        overview = summary_data.get("context_and_overview", "")
        key_takeaways = summary_data.get("key_takeaways", [])
        breakdown = summary_data.get("detailed_breakdown", "")
        action_items = summary_data.get("action_items", [])
        quotes = summary_data.get("notable_quotes", [])

        # Header metadata block: only channel, source video, and generation time in PKT
        md_lines = [
            f"# {video_title}",
            "",
            "> 📌 **Channel:** " + channel_name + "  ",
            f"> 🔗 **Source Video:** [{video_title}]({video_url})  ",
            "> ⏱️ **Summary Generated:** " + gen_date_str + "  ",
            "",
            "---",
            "",
            "### ⚡ Executive One-Sentence Takeaway",
            f"> **{one_sentence}**",
            "",
            "---",
            "",
            "### 🎯 Context & Overview",
            overview if overview else "Concise analysis of core points discussed in the video.",
            "",
            "---",
            "",
            "### 📋 Key Takeaways",
        ]

        for idx, kt in enumerate(key_takeaways, 1):
            md_lines.append(f"- {kt}")

        md_lines.extend([
            "",
            "---",
            "",
            "### 🔍 Detailed Analysis & Deep Dive",
            "",
            breakdown,
            "",
            "---",
            "",
            "### ✅ Action Items & Recommendations",
        ])

        if action_items:
            for item in action_items:
                md_lines.append(f"- [ ] {item}")
        else:
            md_lines.append("- [ ] Review the concepts discussed in the video.")

        if quotes:
            valid_quotes = [q for q in quotes if q.get("quote")]
            if valid_quotes:
                md_lines.extend([
                    "",
                    "---",
                    "",
                    "### 💬 Notable Quotes & Key Statements",
                ])
                for q in valid_quotes:
                    quote_text = q.get("quote", "")
                    quote_ctx = q.get("context_or_timestamp", "Highlight")
                    md_lines.append(f"> \"{quote_text}\" — *{quote_ctx}*")

        # Note: Topics and AI Engine lines are intentionally omitted per user request.

        md_content = "\n".join(md_lines) + "\n"

        # Write the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"Saved summary markdown to: {file_path}")

        # 4. Update Master Index
        cat_display = summary_data.get("category_display", "💡 Tech Summary")
        cls._update_master_index(
            base_dir=base_dir,
            date_str=today_str,
            cat_display=cat_display,
            channel_name=channel_name,
            video_title=video_title,
            video_url=video_url,
            rel_file_path=f"./{today_str}/{filename}",
            one_sentence=one_sentence
        )

        return file_path

    @classmethod
    def _update_master_index(
        cls,
        base_dir: Path,
        date_str: str,
        cat_display: str,
        channel_name: str,
        video_title: str,
        video_url: str,
        rel_file_path: str,
        one_sentence: str
    ):
        """Maintains an up-to-date INDEX.md master table cataloging all summaries."""
        index_file = base_dir / "INDEX.md"
        
        # Clean title for markdown table cell
        clean_title_table = video_title.replace("|", "-").strip()
        clean_takeaway_table = one_sentence.replace("|", "-").replace("\n", " ").strip()

        # Format relative link encoded safely
        rel_link = rel_file_path.replace(" ", "%20")
        new_row = f"| {date_str} | {channel_name} | {cat_display} | [{clean_title_table}]({rel_link}) | [YouTube]({video_url}) | {clean_takeaway_table} |\n"

        if not index_file.exists():
            header = (
                "# 📚 Global Technology Intelligence Library\n\n"
                "This library contains individual Markdown summaries of technology developments gathered from configured official, news, community, and open-source sources.\n\n"
                "| Date | Sources | Category | Summary Document | Primary Source | Key Takeaway |\n"
                "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            )
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(header + new_row)
        else:
            with open(index_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            lines = content.splitlines(keepends=True)
            matching_row = next(
                (i for i, line in enumerate(lines) if rel_link in line),
                None
            )
            if matching_row is not None:
                lines[matching_row] = new_row
                with open(index_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            elif video_url not in content:
                table_split_idx = next(
                    (i + 1 for i, line in enumerate(lines) if line.startswith("| :---")),
                    -1
                )
                if table_split_idx != -1:
                    lines.insert(table_split_idx, new_row)
                    with open(index_file, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                else:
                    with open(index_file, "a", encoding="utf-8") as f:
                        f.write(new_row)

    @classmethod
    def summary_exists_for_video(cls, video_id: str, video_title: str) -> bool:
        """Checks if a markdown summary already exists on disk for this video."""
        base_dir = settings.SUMMARIES_PATH
        if not base_dir.exists():
            return False

        clean_title = cls.sanitize_filename(video_title)
        # Check direct filename match first
        today_str = datetime.now().strftime("%Y-%m-%d")
        direct_match = base_dir / today_str / f"{clean_title}.md"
        if direct_match.exists():
            return True

        for md_file in base_dir.rglob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            if clean_title and clean_title.lower() in md_file.name.lower():
                return True
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    header_chunk = f.read(600)
                    if video_id in header_chunk:
                        return True
            except Exception:
                pass
        return False
