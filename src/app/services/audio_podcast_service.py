import re
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from src.app.config import settings
from src.app.utils.logger import logger

class AudioPodcastService:
    """
    Synthesizes natural, conversational AI audio podcasts (.mp3) from summaries
    using Microsoft Edge's natural neural voices (100% free, zero cost).
    """

    @classmethod
    def clean_text_for_speech(cls, text: str) -> str:
        """Removes markdown symbols, URLs, and formatting for fluid spoken audio."""
        clean = re.sub(r'#+\s*', '', text)
        clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean)
        clean = re.sub(r'[\*_`>]', '', clean)
        clean = re.sub(r'https?://\S+', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    @classmethod
    async def generate_summary_podcast(
        cls,
        video_title: str,
        channel_name: str,
        summary_data: Dict[str, Any],
        output_mp3_path: Path
    ) -> Optional[Path]:
        """Generates a 45-60 second natural audio narration for a single video summary."""
        if not settings.ENABLE_AUDIO_PODCAST:
            return None

        try:
            import edge_tts
        except ImportError:
            logger.debug("edge-tts is not installed. Skipping audio podcast.")
            return None

        one_sentence = cls.clean_text_for_speech(summary_data.get("one_sentence_takeaway", ""))
        overview = cls.clean_text_for_speech(summary_data.get("context_and_overview", ""))
        takeaways = summary_data.get("key_takeaways", [])

        spoken_points = []
        for idx, pt in enumerate(takeaways[:3], 1):
            clean_pt = cls.clean_text_for_speech(pt)
            spoken_points.append(f"Point {idx}: {clean_pt}")

        points_text = " ".join(spoken_points)

        script = (
            f"Here is your executive briefing for {video_title}, published by {channel_name}. "
            f"Bottom line: {one_sentence}. "
            f"{overview} "
            f"Here are the core takeaways: {points_text}. "
            f"This concludes your brief."
        )

        try:
            voice = getattr(settings, "PODCAST_VOICE", "en-US-AndrewMultilingualNeural")
            communicate = edge_tts.Communicate(script, voice)
            output_mp3_path.parent.mkdir(parents=True, exist_ok=True)
            await communicate.save(str(output_mp3_path))
            logger.info(f"Generated AI audio podcast: {output_mp3_path.name}")
            return output_mp3_path
        except Exception as e:
            logger.warning(f"Audio podcast generation failed for '{video_title}': {e}")
            return None

    @classmethod
    async def generate_daily_brief_podcast(
        cls,
        date_str: str,
        briefing_text: str,
        output_mp3_path: Path
    ) -> Optional[Path]:
        """Generates a complete multi-topic audio briefing for the Daily Digest."""
        if not settings.ENABLE_AUDIO_PODCAST:
            return None

        try:
            import edge_tts
        except ImportError:
            return None

        clean_script = cls.clean_text_for_speech(briefing_text)
        # Limit script length to roughly 120-150 words for an exact ~60 second audio duration
        words = clean_script.split()
        if len(words) > 150:
            clean_script = " ".join(words[:145]) + "..."

        try:
            voice = getattr(settings, "PODCAST_VOICE", "ur-PK-AsadNeural")
            communicate = edge_tts.Communicate(clean_script, voice)
            output_mp3_path.parent.mkdir(parents=True, exist_ok=True)
            await communicate.save(str(output_mp3_path))
            logger.info(f"Generated ~60s Hindi/Urdu daily briefing audio podcast: {output_mp3_path.name}")
            return output_mp3_path
        except Exception as e:
            logger.warning(f"Daily audio podcast generation failed: {e}")
            return None
