#!/usr/bin/env python3
"""
Manual Trigger Script for Tech & AI Omnichannel Intelligence & Content Aggregator.
Monitors YouTube, Reddit, Hacker News, GitHub Trending, Tech Blogs, and Frontier AI Labs,
clusters overlapping stories, synthesizes structured Markdown briefs, and exports social suites.
"""

import sys
import argparse
import asyncio
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# Ensure UTF-8 output on Windows console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.app.database import engine, Base
from src.app.config import settings
from src.app.services.job_service import JobService

async def main():
    parser = argparse.ArgumentParser(description="Trigger Tech & AI Intelligence Engine Ingestion")
    parser.add_argument(
        "--mode",
        choices=["omnichannel", "all", "youtube"],
        default="omnichannel",
        help="Pipeline mode: 'omnichannel' (Reddit, HN, GitHub, Labs, Blogs), 'all' (YouTube + Omnichannel), or 'youtube'"
    )
    args = parser.parse_args()

    job_type = "SYNC_OMNICHANNEL"
    if args.mode == "all":
        job_type = "SYNC_ALL"
    elif args.mode == "youtube":
        job_type = "SYNC_YOUTUBE"

    print("=" * 70)
    print("  >> Tech & AI Omnichannel Intelligence & Content Aggregator <<")
    print(f"  Mode:           {args.mode.upper()} ({job_type})")
    print(f"  Sources:        {ROOT_DIR / 'feeds'}")
    print(f"  Summaries Dest: {settings.SUMMARIES_PATH}")
  

    Base.metadata.create_all(bind=engine)
    job_uuid = await JobService.create_and_run_job(job_type)
    print(f"[INFO] Initialized {job_type} job: {job_uuid}")
    print("[INFO] Monitoring feeds, clustering topics, and generating Markdown reports...\n")

    from src.app.database import SessionLocal
    from src.app.models.job import ProcessingJob

    last_log_idx = 0
    while True:
        await asyncio.sleep(2)
        db = SessionLocal()
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.job_uuid == job_uuid).first()
            if job:
                logs = job.logs or []
                while last_log_idx < len(logs):
                    entry = logs[last_log_idx]
                    print(f"[{entry.get('level', 'INFO')}] {entry.get('message', '')}")
                    last_log_idx += 1
                if job.status in ("COMPLETED", "FAILED", "CANCELLED"):
                    print(f"\n[STATUS] Pipeline finished with: {job.status}")
                    if job.status == "FAILED" and job.error_message:
                        print(f"[ERROR] {job.error_message}")
                    break
        finally:
            db.close()

if __name__ == "__main__":
    asyncio.run(main())
