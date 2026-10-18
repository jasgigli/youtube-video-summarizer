from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.app.config import settings
from src.app.services.job_service import JobService
from src.app.utils.logger import logger

class SchedulerService:
    """Automated recurring subscription sync scheduler."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.job_id = "auto_channel_sync"

    def start(self):
        if not settings.ENABLE_SCHEDULER:
            logger.info("Scheduler is disabled by config.")
            return

        if not self.scheduler.running:
            self.scheduler.add_job(
                func=self._trigger_auto_sync,
                trigger=IntervalTrigger(hours=settings.SYNC_INTERVAL_HOURS),
                id=self.job_id,
                name="Automated Channel Subscriptions Sync",
                replace_existing=True
            )
            self.scheduler.start()
            logger.info(f"Subscription auto-sync scheduler started (every {settings.SYNC_INTERVAL_HOURS}h)")

            # Trigger an immediate background check on startup
            import asyncio
            asyncio.create_task(self._trigger_auto_sync())

            # Schedule periodic watcher for channels.json modifications
            self.scheduler.add_job(
                func=self._check_channels_json_modified,
                trigger=IntervalTrigger(seconds=30),
                id="watch_channels_json",
                name="Watch channels.json changes",
                replace_existing=True
            )

            # Schedule Daily Morning Digest (runs every 6 hours or once daily)
            from src.app.services.daily_digest_service import DailyDigestService
            from src.app.services.archive_service import ArchiveService

            self.scheduler.add_job(
                func=DailyDigestService.compile_daily_brief,
                trigger=IntervalTrigger(hours=6),
                id="daily_brief_digest",
                name="Automated Daily Intelligence Briefing",
                replace_existing=True
            )

            # Schedule Weekly Archive Cleanup (runs every 24 hours)
            self.scheduler.add_job(
                func=ArchiveService.run_cleanup,
                trigger=IntervalTrigger(hours=24),
                id="archive_cleanup",
                name="Weekly Summary Archive Cleanup",
                replace_existing=True
            )

    def update_interval(self, hours: int):
        """Dynamically reconfigures interval."""
        if self.scheduler.running and self.scheduler.get_job(self.job_id):
            self.scheduler.reschedule_job(
                self.job_id,
                trigger=IntervalTrigger(hours=hours)
            )
            logger.info(f"Rescheduled auto-sync interval to {hours} hours.")

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown cleanly.")

    async def _check_channels_json_modified(self):
        """Checks if channels.json was modified since last check."""
        try:
            channels_json_path = settings.DATA_PATH.parent / "channels.json"
            if not channels_json_path.exists():
                return
            mtime = channels_json_path.stat().st_mtime
            if not hasattr(self, "_last_channels_mtime"):
                self._last_channels_mtime = mtime
                return
            if mtime > self._last_channels_mtime:
                self._last_channels_mtime = mtime
                logger.info("channels.json was updated! Automatically triggering sync for newly added channels...")
                await self._trigger_auto_sync()
        except Exception as e:
            logger.debug(f"Error checking channels.json: {e}")

    async def _trigger_auto_sync(self):
        logger.info("Scheduled trigger firing: launching SYNC_ALL pipeline...")
        try:
            await JobService.create_and_run_job("SYNC_ALL")
        except Exception as e:
            logger.error(f"Error during scheduled auto sync: {e}")

scheduler_service = SchedulerService()
