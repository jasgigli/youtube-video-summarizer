import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Set, Optional
from fastapi import WebSocket
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models.channel import Channel
from backend.app.models.video import Video
from backend.app.models.summary import Summary
from backend.app.models.job import ProcessingJob
from backend.app.models.setting import Setting
from backend.app.services.youtube_service import YouTubeService
from backend.app.services.transcript_service import TranscriptService
from backend.app.services.llm_service import LLMService
from backend.app.services.whatsapp_service import WhatsAppService
from backend.app.utils.logger import logger

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
    Ensures absolute fault tolerance: errors on a single video or channel
    are recorded and isolated, allowing the pipeline to proceed without interruption.
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
        """Syncs all active subscribed channels and syncs from channels.json if present."""
        # 1. Sync from channels.json if file exists
        channels_json_path = settings.DATA_PATH.parent / "channels.json"
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
                            # Check if exists
                            exists = db.query(Channel).filter(
                                (Channel.custom_url.ilike(handle_str)) |
                                (Channel.custom_url.ilike(handle_str.lstrip("@"))) |
                                (Channel.title.ilike(handle_str.lstrip("@")))
                            ).first()
                            if not exists:
                                try:
                                    resolved = await yt.resolve_channel(handle_str)
                                    db_ch = db.query(Channel).filter(Channel.channel_id == resolved["channel_id"]).first()
                                    if not db_ch:
                                        db_ch = Channel(
                                            channel_id=resolved["channel_id"],
                                            title=resolved["title"],
                                            custom_url=resolved.get("custom_url"),
                                            description=resolved.get("description"),
                                            thumbnail_url=resolved.get("thumbnail_url"),
                                            subscriber_count=resolved.get("subscriber_count", 0),
                                            is_active=True
                                        )
                                        db.add(db_ch)
                                        db.commit()
                                        job.append_log(f"Auto-imported channel '{resolved['title']}' from channels.json", "INFO")
                                except Exception as err:
                                    logger.warning(f"Could not auto-import '{handle_str}' from channels.json: {err}")
            except Exception as e:
                logger.error(f"Error reading channels.json: {e}")

        channels = db.query(Channel).filter(Channel.is_active == True).all()
        if not channels:
            job.append_log("No active channels found to sync. Add channels to channels.json or database.", "WARNING")
            job.current_step = "No active channels to process"
            db.commit()
            return

        job.append_log(f"Found {len(channels)} active channels to scan.", "INFO")
        for idx, channel in enumerate(channels, 1):
            job.current_step = f"Processing channel {idx}/{len(channels)}: {channel.title}"
            job.append_log(f"Scanning channel '{channel.title}' ({channel.channel_id})...", "INFO")
            db.commit()
            await cls._emit_progress(job, f"Scanning {channel.title}")

            try:
                await cls._process_single_channel_videos(db, job, channel)
            except Exception as e:
                # Fault tolerance: channel failure does NOT interrupt remaining channels!
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
        """Fetches videos, extracts transcripts, and synthesizes summaries."""
        # Read API key and max videos setting (default: 1 newest video only)
        api_key_setting = db.query(Setting).filter(Setting.key == "youtube_api_key").first()
        max_videos_setting = db.query(Setting).filter(Setting.key == "max_videos_per_channel").first()
        sync_limit = int(max_videos_setting.value) if max_videos_setting else settings.MAX_VIDEOS_PER_CHANNEL_SYNC
        sync_limit = max(1, sync_limit)

        yt_service = YouTubeService(api_key=api_key_setting.value if api_key_setting else None)

        # 1. Fetch latest videos from channel (channel page scraping / RSS / API)
        raw_videos = await yt_service.fetch_latest_videos(
            channel_id=channel.channel_id,
            custom_url=channel.custom_url,
            limit=sync_limit
        )
        # Strictly keep only the newest published video(s)
        raw_videos = raw_videos[:sync_limit]
        channel.last_synced_at = datetime.utcnow()
        db.commit()

        if not raw_videos:
            job.append_log(f"No recent videos found for channel '{channel.title}'.", "INFO")
            return

        job.append_log(f"Retrieved newest {len(raw_videos)} video for '{channel.title}'. Ingesting...", "INFO")

        # 2. Ingest or update videos
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

            # Process summary if pending or failed
            if video.summary_status in ("PENDING", "FAILED"):
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
        """Processes transcript retrieval and LLM summarization for one video."""
        job.current_step = f"Processing video: {video.title[:45]}..."
        job.append_log(f"Starting pipeline for video '{video.title}' ({video.video_id})", "INFO")
        db.commit()
        await cls._emit_progress(job, f"Ingesting: {video.title[:30]}")

        # 1. Fetch transcript if not already cached
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
                    f"Captions {t_res['status']} on YouTube. Fetching creator description & metadata...",
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
                    f"(Note: Synthesize the executive summary and key insights based on the video title and creator description.)"
                )

        # 2. Synthesize with LLM
        video.summary_status = "PROCESSING"
        db.commit()
        await cls._emit_progress(job, f"Synthesizing: {video.title[:30]}")

        # Resolve configured provider and keys
        provider_setting = db.query(Setting).filter(Setting.key == "default_provider").first()
        provider = provider_setting.value if provider_setting else settings.DEFAULT_PROVIDER
        
        key_name = f"{provider}_api_key"
        key_setting = db.query(Setting).filter(Setting.key == key_name).first()
        api_key = key_setting.value if key_setting else None

        job.append_log(f"Generating structured takeaways using provider '{provider}'...", "INFO")
        llm = LLMService(provider=provider, api_key=api_key)

        try:
            summary_data = await llm.summarize_video(
                title=video.title,
                channel_name=channel_title,
                transcript=transcript_content
            )

            # Check if summary already exists
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
            job.append_log(f"Successfully summarized '{video.title}' ({summary_data.get('processing_time_sec')}s)", "INFO")
            db.commit()

            # 1. Automated direct WhatsApp delivery
            phone_val = settings.WHATSAPP_PHONE_NUMBER
            phone_setting = db.query(Setting).filter(Setting.key == "whatsapp_phone").first()
            if phone_setting and phone_setting.value:
                phone_val = phone_setting.value

            job.append_log(f"Delivering summary directly to WhatsApp ({phone_val})...", "INFO")
            sent = await asyncio.to_thread(
                WhatsAppService.send_summary_direct,
                phone=phone_val,
                video_title=video.title,
                channel_name=channel_title,
                video_url=video.video_url,
                one_sentence_takeaway=summary_data["one_sentence_takeaway"],
                key_takeaways=summary_data["key_takeaways"],
                action_items=summary_data.get("action_items"),
                published_at=video.published_at
            )
            if sent:
                job.append_log(f"Summary successfully delivered directly to your WhatsApp!", "INFO")

            # 2. Emit summary completion event to connected frontend clients
            summary_entity = db.query(Summary).filter(Summary.video_id == video.id).first()
            if summary_entity:
                await cls._emit_summary_ready(video, channel_title, summary_entity)

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
    async def _emit_summary_ready(cls, video: Video, channel_title: str, summary: Summary):
        """Broadcasts a ready-to-share summary to connected clients for automatic WhatsApp dispatch."""
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
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        await ws_manager.broadcast(payload)
