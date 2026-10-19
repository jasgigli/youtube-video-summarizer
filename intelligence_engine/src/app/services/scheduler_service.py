from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.app.config import settings
from src.app.database import SessionLocal
from src.app.models.job import ProcessingJob
from src.app.services.job_service import JobService
from src.app.utils.logger import logger

class SchedulerService:
    """Automated recurring global technology intelligence sync scheduler."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.job_id = "auto_omnichannel_sync"

    def start(self):
        if not settings.ENABLE_SCHEDULER:
            logger.info("Scheduler is disabled by config.")
            return

        if not self.scheduler.running:
            self.scheduler.add_job(
                func=self._trigger_auto_sync,
                trigger=IntervalTrigger(hours=settings.SYNC_INTERVAL_HOURS),
                id=self.job_id,
                name="Automated Global Technology Intelligence Sync",
                replace_existing=True
            )
            self.scheduler.start()
            logger.info(f"Global intelligence scheduler started (every {settings.SYNC_INTERVAL_HOURS}h)")

            # Collect current global technology developments at startup.
            import asyncio
            asyncio.create_task(self._trigger_auto_sync())

            # Rebuild the daily summary from collected global intelligence.
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

    async def _trigger_auto_sync(self):
        logger.info("Scheduled trigger firing: launching global omnichannel intelligence pipeline...")
        db = SessionLocal()
        try:
            active_job = db.query(ProcessingJob).filter(
                ProcessingJob.status.in_(("QUEUED", "RUNNING"))
            ).first()
            if active_job:
                logger.info(
                    f"Skipping scheduled sync while job {active_job.job_uuid} "
                    f"({active_job.job_type}) is {active_job.status}."
                )
                return
        finally:
            db.close()

        try:
            await JobService.create_and_run_job("SYNC_OMNICHANNEL")
        except Exception as e:
            logger.error(f"Error during scheduled auto sync: {e}")

scheduler_service = SchedulerService()
