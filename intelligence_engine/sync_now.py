"""
sync_now.py — One-shot command-line trigger for the Intelligence Engine.

Fetches today's news/updates from all configured feeds, deduplicates,
clusters, summarizes via Gemini, and writes individual .md reports plus
a consolidated DAILY_BRIEF.md into summaries/YYYY-MM-DD/.

Usage:
    python sync_now.py                     # Omnichannel feeds only
    python sync_now.py --mode omnichannel  # Same as above
    python sync_now.py --mode all          # YouTube channels + Omnichannel feeds
    python sync_now.py --mode youtube      # YouTube channels only
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import date

# Ensure the project root is on sys.path so `src.app.*` imports resolve.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env before importing anything that reads settings.
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.app.config import settings
from src.app.database import engine, Base, SessionLocal
from src.app.services.job_service import JobService
from src.app.utils.logger import logger


def _ensure_db():
    """Create tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


async def _run_pipeline(mode: str):
    """Execute the requested ingestion pipeline as a one-shot job."""
    _ensure_db()

    today = date.today().isoformat()
    logger.info("=" * 70)
    logger.info(f"  Intelligence Engine — One-Shot Sync")
    logger.info(f"  Date:  {today}")
    logger.info(f"  Mode:  {mode.upper()}")
    logger.info(f"  Feeds: {settings.FEEDS_CONFIG_PATH}")
    logger.info(f"  Output: {settings.SUMMARIES_PATH / today}")
    logger.info("=" * 70)

    job_type_map = {
        "omnichannel": "SYNC_OMNICHANNEL",
        "all": "SYNC_ALL",
        "youtube": "SYNC_YOUTUBE",
    }
    job_type = job_type_map.get(mode.lower(), "SYNC_OMNICHANNEL")

    job_uuid = await JobService.create_and_run_job(job_type)
    logger.info(f"Job {job_uuid} dispatched ({job_type}). Waiting for completion...")

    # Poll until the job finishes (fire-and-forget inside create_and_run_job
    # will run in the same event loop).
    from src.app.models.job import ProcessingJob
    while True:
        await asyncio.sleep(3)
        db = SessionLocal()
        try:
            job = db.query(ProcessingJob).filter(
                ProcessingJob.job_uuid == job_uuid
            ).first()
            if not job:
                logger.error("Job record disappeared.")
                break
            if job.status in ("COMPLETED", "FAILED", "CANCELLED"):
                logger.info(f"Job finished: {job.status}")
                logger.info(f"  Processed: {job.processed_items}  |  Errors: {job.failed_items}")
                if job.status == "FAILED" and job.error_message:
                    logger.error(f"  Error: {job.error_message}")
                break
        finally:
            db.close()

    logger.info("Sync complete. Check summaries/ for today's reports.")


def main():
    parser = argparse.ArgumentParser(
        description="Intelligence Engine — One-shot pipeline trigger"
    )
    parser.add_argument(
        "--mode",
        choices=["omnichannel", "all", "youtube"],
        default="omnichannel",
        help="Which pipeline to run (default: omnichannel)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_run_pipeline(args.mode))
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
