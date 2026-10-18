import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Set, Optional
from fastapi import WebSocket
from sqlalchemy.orm import Session

from src.app.config import settings
from src.app.database import SessionLocal
from src.app.models.channel import Channel
from src.app.models.video import Video
from src.app.models.summary import Summary
from src.app.models.job import ProcessingJob
from src.app.models.setting import Setting
from src.app.services.youtube_service import YouTubeService
from src.app.services.transcript_service import TranscriptService
from src.app.services.llm_service import LLMService
from src.app.services.markdown_storage_service import MarkdownStorageService
from src.app.services.notification_service import NotificationService
from src.app.services.audio_podcast_service import AudioPodcastService
from src.app.services.git_sync_service import GitSyncService
from src.app.services.social_content_service import SocialContentService
from src.app.utils.logger import logger

class WebSocketConnectionManager:
    """Manages active WebSocket connections for streaming pipeline updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dc in dead_connections:
            self.disconnect(dc)

ws_manager = WebSocketConnectionManager()

class JobService:
    """
    Background job execution coordinator.
    Ensures fault tolerance: errors on a single video or channel are isolated.
    Fetches latest videos from channels in channels.json, categorizes them,
    synthesizes tailored summaries, and stores them in Markdown format.
    """

    @classmethod
    async def create_and_run_job(
        cls,
        job_type: str,
        target_identifier: Optional[str] = None
    ) -> str:
        """Creates a background job in DB and launches async execution."""
        job_uuid = str(uuid.uuid4())
        db = SessionLocal()
        try:
            job = ProcessingJob(
                job_uuid=job_uuid,
                job_type=job_type,
                target_identifier=target_identifier,
                status="QUEUED",
                current_step="Job queued for processing",
                created_at=datetime.utcnow()
            )
            job.append_log(f"Initialized job {job_type}", "INFO")
            db.add(job)
            db.commit()
            db.refresh(job)
        finally:
            db.close()

        # Fire and forget background worker
        asyncio.create_task(cls._execute_job(job_uuid, job_type, target_identifier))
        return job_uuid

    @classmethod
    async def _execute_job(cls, job_uuid: str, job_type: str, target_identifier: Optional[str]):
        """Dispatches job to specialized handler."""
        db = SessionLocal()
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.job_uuid == job_uuid).first()
            if not job:
                return

            job.status = "RUNNING"
            job.started_at = datetime.utcnow()
            job.append_log("Starting pipeline execution...", "INFO")
            db.commit()

            await cls._emit_progress(job, "Pipeline started")

            if job_type == "SYNC_ALL":
                await cls._run_sync_all(db, job)
            elif job_type == "SYNC_CHANNEL":
                await cls._run_sync_channel(db, job, target_identifier)
            elif job_type == "SUMMARIZE_VIDEO":
                await cls._run_summarize_video(db, job, target_identifier)
            else:
                job.append_log(f"Unknown job type: {job_type}", "ERROR")

            job.status = "COMPLETED" if job.status != "CANCELLED" else "CANCELLED"
            job.completed_at = datetime.utcnow()
            job.current_step = f"Pipeline finished. Processed: {job.processed_items}, Errors/Skipped: {job.failed_items}"
            job.append_log(job.current_step, "INFO")
            db.commit()

            await cls._emit_progress(job, "Pipeline finished")

        except Exception as e:
            logger.error(f"Fatal error in job {job_uuid}: {str(e)}", exc_info=True)
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                job.append_log(f"Pipeline crashed with error: {str(e)}", "ERROR")
                db.commit()
                await cls._emit_progress(job, "Pipeline encountered fatal error")
        finally:
            db.close()

    @classmethod
    async def _run_sync_all(cls, db: Session, job: ProcessingJob):
        """
        Syncs strictly from the channels specified in channels.json.
        Only fetches the latest video per channel and saves readable Markdown summaries.
        """
        channels_json_path = settings.DATA_PATH.parent / "channels.json"
        target_channels: List[Channel] = []

        if channels_json_path.exists():
            try:
                import json
                with open(channels_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    c_list = data.get("channels", [])
                    if c_list:
                        api_key_setting = db.query(Setting).filter(Setting.key == "youtube_api_key").first()
                        yt = YouTubeService(api_key=api_key_setting.value if api_key_setting else None)
                        for handle in c_list:
                            handle_str = handle.strip()
                            if not handle_str:
                                continue
                            
                            # Match in DB
                            ch = db.query(Channel).filter(
                                (Channel.custom_url.ilike(handle_str)) |
                                (Channel.custom_url.ilike(handle_str.lstrip("@"))) |
                                (Channel.title.ilike(handle_str.lstrip("@")))
                            ).first()

                            if not ch:
                                try:
                                    resolved = await yt.resolve_channel(handle_str)
                                    ch = db.query(Channel).filter(Channel.channel_id == resolved["channel_id"]).first()
                                    if not ch:
                                        ch = Channel(
                                            channel_id=resolved["channel_id"],
                                            title=resolved["title"],
                                            custom_url=resolved.get("custom_url"),
                                            description=resolved.get("description"),
                                            thumbnail_url=resolved.get("thumbnail_url"),
                                            subscriber_count=resolved.get("subscriber_count", 0),
                                            is_active=True
                                        )
                                        db.add(ch)
                                        db.commit()
                                        db.refresh(ch)
                                        job.append_log(f"Imported channel '{resolved['title']}' from channels.json", "INFO")
                                except Exception as err:
                                    logger.warning(f"Could not resolve handle '{handle_str}' from channels.json: {err}")

                            if ch and ch not in target_channels:
                                target_channels.append(ch)
            except Exception as e:
                logger.error(f"Error reading channels.json: {e}")

        # Fallback to all active channels in DB if channels.json was empty
        if not target_channels:
            target_channels = db.query(Channel).filter(Channel.is_active == True).all()

        if not target_channels:
            job.append_log("No channels found to sync. Add channels to channels.json.", "WARNING")
            job.current_step = "No channels to process"
            db.commit()
            return

        job.append_log(f"Found {len(target_channels)} channels from channels.json to scan.", "INFO")
        for idx, channel in enumerate(target_channels, 1):
            job.current_step = f"Processing channel {idx}/{len(target_channels)}: {channel.title}"
            job.append_log(f"Scanning channel '{channel.title}'...", "INFO")
            db.commit()
            await cls._emit_progress(job, f"Scanning {channel.title}")

            try:
                await cls._process_single_channel_videos(db, job, channel)
            except Exception as e:
                job.failed_items += 1
                job.append_log(f"Error processing channel '{channel.title}': {str(e)}", "ERROR")
                db.commit()

    @classmethod
    async def _run_sync_channel(cls, db: Session, job: ProcessingJob, channel_identifier: Optional[str]):
        """Syncs a single channel by ID or handle."""
        channel = None
        if channel_identifier:
            if channel_identifier.isdigit():
                channel = db.query(Channel).filter(Channel.id == int(channel_identifier)).first()
            else:
                channel = db.query(Channel).filter(
                    (Channel.channel_id == channel_identifier) | 
                    (Channel.custom_url == channel_identifier)
                ).first()

        if not channel:
            job.append_log(f"Channel '{channel_identifier}' not found in database.", "ERROR")
            job.status = "FAILED"
            db.commit()
            return

        job.append_log(f"Syncing videos for '{channel.title}'...", "INFO")
        await cls._process_single_channel_videos(db, job, channel)

    @classmethod
    async def _process_single_channel_videos(cls, db: Session, job: ProcessingJob, channel: Channel):
        """Fetches the latest single video from the channel, checks for updates, and summarizes."""
        api_key_setting = db.query(Setting).filter(Setting.key == "youtube_api_key").first()
        max_videos_setting = db.query(Setting).filter(Setting.key == "max_videos_per_channel").first()
        sync_limit = int(max_videos_setting.value) if max_videos_setting else settings.MAX_VIDEOS_PER_CHANNEL_SYNC
        sync_limit = max(1, sync_limit)

        yt_service = YouTubeService(api_key=api_key_setting.value if api_key_setting else None)

        # 1. Fetch latest video from channel
        raw_videos = await yt_service.fetch_latest_videos(
            channel_id=channel.channel_id,
            custom_url=channel.custom_url,
            limit=sync_limit
        )
        raw_videos = raw_videos[:sync_limit]
        channel.last_synced_at = datetime.utcnow()
        db.commit()

        if not raw_videos:
            job.append_log(f"No recent videos found for channel '{channel.title}'.", "INFO")
            return

        # 2. Ingest or check video
        for vdata in raw_videos:
            existing = db.query(Video).filter(Video.video_id == vdata["video_id"]).first()
            if not existing:
                video = Video(
                    video_id=vdata["video_id"],
                    channel_id=channel.id,
                    title=vdata["title"],
                    description=vdata.get("description", ""),
                    published_at=vdata["published_at"],
                    thumbnail_url=vdata.get("thumbnail_url"),
                    video_url=vdata["video_url"],
                    duration_seconds=vdata.get("duration_seconds", 0),
                    transcript_status="PENDING",
                    summary_status="PENDING"
                )
                db.add(video)
                db.commit()
                db.refresh(video)
            else:
                video = existing

            # Check if markdown document already exists on disk
            has_md = MarkdownStorageService.summary_exists_for_video(video.video_id, video.title)
            if video.summary_status == "COMPLETED" and has_md:
                job.append_log(f"Latest video '{video.title[:40]}' already summarized in Markdown. Skipping.", "INFO")
                continue

            # Process summary if pending or if markdown file doesn't exist yet
            job.total_items += 1
            db.commit()
            await cls._process_single_video(db, job, video, channel.title)

    @classmethod
    async def _run_summarize_video(cls, db: Session, job: ProcessingJob, video_identifier: Optional[str]):
        """Summarizes a specific video by ID."""
        video = None
        if video_identifier:
            if video_identifier.isdigit():
                video = db.query(Video).filter(Video.id == int(video_identifier)).first()
            else:
                video = db.query(Video).filter(Video.video_id == video_identifier).first()

        if not video:
            job.append_log(f"Video '{video_identifier}' not found.", "ERROR")
            job.status = "FAILED"
            db.commit()
            return

        channel_title = video.channel.title if video.channel else "YouTube Channel"
        job.total_items = 1
        db.commit()
        await cls._process_single_video(db, job, video, channel_title, force_regenerate=True)

    @classmethod
    async def _process_single_video(
        cls,
        db: Session,
        job: ProcessingJob,
        video: Video,
        channel_title: str,
        force_regenerate: bool = False
    ):
        """Processes transcript retrieval, LLM summarization, and Markdown storage."""
        job.current_step = f"Processing: {video.title[:45]}..."
        job.append_log(f"Starting pipeline for '{video.title}' ({video.video_id})", "INFO")
        db.commit()
        await cls._emit_progress(job, f"Ingesting: {video.title[:30]}")

        # 1. Fetch transcript if not cached
        transcript_content = video.transcript_text
        if not transcript_content or force_regenerate:
            job.append_log(f"Extracting captions for '{video.title}'...", "INFO")
            t_res = await TranscriptService.fetch_transcript(video.video_id)
            video.transcript_status = t_res["status"]
            video.transcript_language = t_res.get("language")
            video.transcript_error = t_res.get("error")

            if t_res["status"] == "SUCCESS" and t_res.get("text"):
                video.transcript_text = t_res["text"]
                transcript_content = t_res["text"]
                db.commit()
            else:
                job.append_log(
                    f"Captions unavailable on YouTube ({t_res.get('status')}). Using metadata fallback...",
                    "INFO"
                )
                if not video.description or len(video.description.strip()) < 15:
                    meta = await asyncio.to_thread(TranscriptService.fetch_video_metadata, video.video_id)
                    if meta.get("description"):
                        video.description = meta["description"]
                        db.commit()

                transcript_content = (
                    f"Video Title: {video.title}\n"
                    f"Channel: {channel_title}\n\n"
                    f"Detailed Creator Description & Overview:\n"
                    f"{video.description or video.title}\n\n"
                    f"(Note: Synthesize the category-tailored analysis based on video title and creator overview.)"
                )

        # 2. Synthesize with LLM
        video.summary_status = "PROCESSING"
        db.commit()
        await cls._emit_progress(job, f"Synthesizing: {video.title[:30]}")

        provider_setting = db.query(Setting).filter(Setting.key == "default_provider").first()
        provider = provider_setting.value if provider_setting else settings.DEFAULT_PROVIDER
        
        key_name = f"{provider}_api_key"
        key_setting = db.query(Setting).filter(Setting.key == key_name).first()
        api_key = key_setting.value if key_setting else None

        job.append_log(f"Synthesizing category-adaptive summary via '{provider}'...", "INFO")
        llm = LLMService(provider=provider, api_key=api_key)

        try:
            summary_data = await llm.summarize_video(
                title=video.title,
                channel_name=channel_title,
                transcript=transcript_content
            )

            # Check or create DB summary
            existing_summary = db.query(Summary).filter(Summary.video_id == video.id).first()
            if existing_summary:
                existing_summary.provider = summary_data["provider"]
                existing_summary.model_name = summary_data["model_name"]
                existing_summary.one_sentence_takeaway = summary_data["one_sentence_takeaway"]
                existing_summary.key_takeaways = summary_data["key_takeaways"]
                existing_summary.detailed_breakdown = summary_data["detailed_breakdown"]
                existing_summary.action_items = summary_data["action_items"]
                existing_summary.notable_quotes = summary_data["notable_quotes"]
                existing_summary.topics = summary_data["topics"]
                existing_summary.sentiment = summary_data.get("sentiment", "informative")
                existing_summary.tokens_used = summary_data.get("tokens_used", 0)
                existing_summary.processing_time_sec = summary_data.get("processing_time_sec", 0.0)
            else:
                summary = Summary(
                    video_id=video.id,
                    provider=summary_data["provider"],
                    model_name=summary_data["model_name"],
                    one_sentence_takeaway=summary_data["one_sentence_takeaway"],
                    detailed_breakdown=summary_data["detailed_breakdown"],
                    sentiment=summary_data.get("sentiment", "informative"),
                    tokens_used=summary_data.get("tokens_used", 0),
                    processing_time_sec=summary_data.get("processing_time_sec", 0.0)
                )
                summary.key_takeaways = summary_data["key_takeaways"]
                summary.action_items = summary_data["action_items"]
                summary.notable_quotes = summary_data["notable_quotes"]
                summary.topics = summary_data["topics"]
                db.add(summary)

            video.summary_status = "COMPLETED"
            video.summary_error = None
            job.processed_items += 1
            db.commit()

            # 3. Save as readable Markdown document and update summaries/INDEX.md
            saved_file = await asyncio.to_thread(
                MarkdownStorageService.save_summary_markdown,
                video_title=video.title,
                channel_name=channel_title,
                video_url=video.video_url,
                video_id=video.video_id,
                published_at=video.published_at,
                summary_data=summary_data
            )

            job.append_log(
                f"[{summary_data.get('category_display', 'Summary')}] Saved to Markdown: {saved_file.name}",
                "INFO"
            )

            # 4. Generate 1-Click Multi-Platform Social Media Suite
            if getattr(settings, "ENABLE_SOCIAL_POST_EXPORT", True):
                try:
                    await asyncio.to_thread(
                        SocialContentService.generate_and_save_social_suite,
                        video_title=video.title,
                        channel_name=channel_title,
                        video_url=video.video_url,
                        video_id=video.video_id,
                        summary_data=summary_data
                    )
                except Exception as soc_err:
                    logger.debug(f"Social media suite generation notice: {soc_err}")

            # 5. Native Windows Desktop Toast Notification
            try:
                NotificationService.notify_video_summarized(channel_title, video.title)
            except Exception as notify_err:
                logger.debug(f"Notification notice: {notify_err}")

            # 6. Auto Git Backup & Sync
            try:
                GitSyncService.sync_summaries()
            except Exception as git_err:
                logger.debug(f"Git sync notice: {git_err}")

            # 7. Broadcast event
            summary_entity = db.query(Summary).filter(Summary.video_id == video.id).first()
            if summary_entity:
                await cls._emit_summary_ready(video, channel_title, summary_entity, str(saved_file))

        except Exception as e:
            logger.error(f"Failed to generate summary for '{video.title}': {str(e)}")
            video.summary_status = "FAILED"
            video.summary_error = str(e)
            job.failed_items += 1
            job.append_log(f"Summary generation error for '{video.title}': {str(e)}", "ERROR")
            db.commit()

    @classmethod
    async def _emit_progress(cls, job: ProcessingJob, stage_desc: str):
        """Broadcasts live progress payload to all connected WebSockets."""
        payload = {
            "type": "JOB_UPDATE",
            "job_uuid": job.job_uuid,
            "job_type": job.job_type,
            "status": job.status,
            "current_step": job.current_step,
            "stage_desc": stage_desc,
            "total_items": job.total_items,
            "processed_items": job.processed_items,
            "failed_items": job.failed_items,
            "recent_log": job.logs[-1] if job.logs else None,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        await ws_manager.broadcast(payload)

    @classmethod
    async def _emit_summary_ready(cls, video: Video, channel_title: str, summary: Summary, markdown_path: Optional[str] = None):
        """Broadcasts summary ready event."""
        payload = {
            "type": "VIDEO_SUMMARIZED",
            "video": {
                "id": video.id,
                "video_id": video.video_id,
                "title": video.title,
                "video_url": video.video_url,
                "channel": {"title": channel_title}
            },
            "summary": {
                "one_sentence_takeaway": summary.one_sentence_takeaway,
                "key_takeaways": summary.key_takeaways,
                "action_items": summary.action_items,
                "provider": summary.provider,
                "model_name": summary.model_name
            },
            "markdown_path": markdown_path,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        await ws_manager.broadcast(payload)
