import asyncio
from typing import Dict, Any, Optional, List
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    IpBlocked,
    RequestBlocked,
    YouTubeRequestFailed,
    YouTubeTranscriptApiException
)
from src.app.utils.logger import logger
from src.app.utils.text_cleaner import format_transcript_with_timestamps

class TranscriptService:
    """
    Fault-tolerant transcript fetching engine.
    Safely captures manual and auto-generated transcripts across languages,
    normalizes output, and isolates errors without halting the processing pipeline.
    """

    @classmethod
    async def fetch_transcript(cls, video_id: str) -> Dict[str, Any]:
        """
        Async wrapper for transcript extraction.
        Runs synchronous library in a background worker thread to prevent event loop blocking.
        """
        return await asyncio.to_thread(cls._fetch_transcript_sync, video_id)

    @classmethod
    def fetch_video_metadata(cls, video_id: str) -> Dict[str, Any]:
        """Fetches full video description and metadata via yt-dlp."""
        try:
            import yt_dlp
            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return {
                    "title": info.get("title"),
                    "description": info.get("description", ""),
                    "tags": info.get("tags", []),
                    "duration": info.get("duration", 0)
                }
        except Exception as e:
            logger.warning(f"Metadata extraction notice for {video_id}: {e}")
            return {"description": "", "tags": []}

    @classmethod
    def _fetch_transcript_sync(cls, video_id: str) -> Dict[str, Any]:
        """
        Synchronous transcript retrieval with multi-language fallback
        and comprehensive exception handling.
        """
        try:
            api_instance = YouTubeTranscriptApi() if callable(YouTubeTranscriptApi) else YouTubeTranscriptApi

            # 1. First attempt: Direct fetch via modern instance API
            try:
                fetched = api_instance.fetch(video_id, languages=('en', 'en-US', 'en-GB'))
                raw_snippets = []
                if hasattr(fetched, 'snippets'):
                    for s in fetched.snippets:
                        raw_snippets.append({
                            'text': getattr(s, 'text', ''),
                            'start': getattr(s, 'start', 0),
                            'duration': getattr(s, 'duration', 0)
                        })
                elif hasattr(fetched, 'to_raw_data'):
                    raw_snippets = fetched.to_raw_data()
                elif isinstance(fetched, list):
                    raw_snippets = fetched

                if raw_snippets:
                    clean_text = format_transcript_with_timestamps(raw_snippets)
                    return {
                        "status": "SUCCESS",
                        "text": clean_text,
                        "language": getattr(fetched, "language_code", "en"),
                        "error": None
                    }
            except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
                raise
            except Exception:
                # Fall through to transcript listing & translation attempt
                pass

            # 2. Advanced attempt: list available transcripts
            transcript_list = None
            if hasattr(api_instance, 'list'):
                transcript_list = api_instance.list(video_id)
            elif hasattr(YouTubeTranscriptApi, 'list_transcripts'):
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            if transcript_list:
                transcript = None
                # Check manual
                try:
                    transcript = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
                except Exception:
                    pass

                # Check generated
                if not transcript:
                    try:
                        transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                    except Exception:
                        pass

                # Fallback: translate any translatable transcript to English
                if not transcript:
                    try:
                        for t in transcript_list:
                            if getattr(t, 'is_translatable', False):
                                transcript = t.translate('en')
                                break
                            else:
                                transcript = t
                                break
                    except Exception:
                        pass

                if transcript:
                    items = transcript.fetch()
                    raw_items = []
                    if hasattr(items, 'snippets'):
                        for s in items.snippets:
                            raw_items.append({'text': getattr(s, 'text', ''), 'start': getattr(s, 'start', 0)})
                    elif isinstance(items, list):
                        raw_items = items

                    clean_text = format_transcript_with_timestamps(raw_items)
                    return {
                        "status": "SUCCESS",
                        "text": clean_text,
                        "language": getattr(transcript, "language_code", "en"),
                        "error": None
                    }

            return {
                "status": "UNAVAILABLE",
                "text": None,
                "language": None,
                "error": "No transcript available in requested languages."
            }

        except Exception as primary_err:
            logger.info(f"Video {video_id}: Primary transcript retrieval notice ({type(primary_err).__name__}). Trying yt-dlp fallback captions...")
            fallback_res = cls._fetch_ytdlp_captions(video_id)
            if fallback_res:
                return fallback_res

            if isinstance(primary_err, TranscriptsDisabled):
                logger.info(f"Video {video_id}: Transcripts are disabled by creator.")
                return {
                    "status": "DISABLED",
                    "text": None,
                    "language": None,
                    "error": "Transcripts are explicitly disabled by the video creator."
                }
            elif isinstance(primary_err, NoTranscriptFound):
                logger.info(f"Video {video_id}: No transcript found.")
                return {
                    "status": "UNAVAILABLE",
                    "text": None,
                    "language": None,
                    "error": "No transcript available in requested languages."
                }
            elif isinstance(primary_err, VideoUnavailable):
                logger.warning(f"Video {video_id}: Video is private or unavailable.")
                return {
                    "status": "UNAVAILABLE",
                    "text": None,
                    "language": None,
                    "error": "Video is private, restricted, or no longer available."
                }
            elif isinstance(primary_err, (IpBlocked, RequestBlocked, YouTubeRequestFailed)):
                logger.warning(f"Video {video_id}: YouTube IP or request blocked: {primary_err}")
                return {
                    "status": "ERROR",
                    "text": None,
                    "language": None,
                    "error": f"YouTube rate-limited or blocked request: {str(primary_err)}"
                }
            else:
                logger.warning(f"Video {video_id}: Unexpected transcript error: {str(primary_err)}")
                return {
                    "status": "UNAVAILABLE",
                    "text": None,
                    "language": None,
                    "error": str(primary_err)
                }

    @classmethod
    def _fetch_ytdlp_captions(cls, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Fallback caption extractor using yt-dlp.
        Retrieves JSON3 timed text for manual or automatic captions directly from YouTube.
        """
        try:
            import urllib.request
            import json
            import yt_dlp

            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
            }
            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                subtitles = info.get('subtitles', {})
                auto_captions = info.get('automatic_captions', {})

                # Check manual English subtitles first, then automatic English, then any available
                target_lang = None
                formats = None

                for lang in ['en', 'en-US', 'en-GB']:
                    if lang in subtitles:
                        target_lang = lang
                        formats = subtitles[lang]
                        break
                if not formats:
                    for lang in ['en', 'en-US', 'en-GB']:
                        if lang in auto_captions:
                            target_lang = lang
                            formats = auto_captions[lang]
                            break

                if not formats:
                    # Grab first available language
                    if subtitles:
                        target_lang = next(iter(subtitles))
                        formats = subtitles[target_lang]
                    elif auto_captions:
                        target_lang = next(iter(auto_captions))
                        formats = auto_captions[target_lang]

                if not formats:
                    return None

                json3_url = None
                for fmt in formats:
                    if fmt.get('ext') == 'json3':
                        json3_url = fmt.get('url')
                        break

                if not json3_url:
                    return None

                req = urllib.request.Request(
                    json3_url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))

                raw_snippets = []
                for event in data.get('events', []):
                    t_start = event.get('tStartMs', 0) / 1000.0
                    t_dur = event.get('dDurationMs', 0) / 1000.0
                    text_parts = [seg.get('utf8', '') for seg in event.get('segs', []) if seg.get('utf8')]
                    seg_text = ''.join(text_parts).strip()
                    if seg_text and seg_text != '\n':
                        raw_snippets.append({
                            'text': seg_text,
                            'start': t_start,
                            'duration': t_dur
                        })

                if raw_snippets:
                    clean_text = format_transcript_with_timestamps(raw_snippets)
                    logger.info(f"Successfully extracted {len(raw_snippets)} caption snippets via yt-dlp fallback for {video_id}")
                    return {
                        "status": "SUCCESS",
                        "text": clean_text,
                        "language": target_lang or "en",
                        "error": None
                    }
        except Exception as e:
            logger.debug(f"yt-dlp caption fallback failed for {video_id}: {e}")

        return None

