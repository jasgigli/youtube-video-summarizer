#!/usr/bin/env python3
"""
Manual Trigger Script for YouTube Video Summarizer.
Executes an immediate SYNC_ALL across channels.json and prints live logs.
"""

import sys
import asyncio
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# Ensure UTF-8 output on Windows console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.app.database import engine, Base
from src.app.services.job_service import JobService

async def main():
    print("=" * 65)
    print("  >> YouTube Video Summarizer — Immediate Manual Sync <<")
    print(f"  Target: {ROOT_DIR / 'channels.json'}")
    print(f"  Destination: {ROOT_DIR / 'summaries'}")
    print("=" * 65)

    Base.metadata.create_all(bind=engine)
    job_uuid = await JobService.create_and_run_job("SYNC_ALL")
    print(f"[INFO] Initialized SYNC_ALL job: {job_uuid}")
    print("[INFO] Scanning channels and generating Markdown summaries...\n")

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
