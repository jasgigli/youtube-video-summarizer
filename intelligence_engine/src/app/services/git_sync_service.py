import os
import sys
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from src.app.config import settings
from src.app.utils.logger import logger

class GitSyncService:
    """
    Automated Git version control and backup service.
    Automatically commits newly generated Markdown summaries and index files,
    and pushes to remote (GitHub) if a remote is configured.
    """

    @classmethod
    def sync_summaries(cls):
        """Stages summaries, commits with timestamp, and pushes if remote exists."""
        if not settings.ENABLE_AUTO_GIT_SYNC:
            return

        base_dir = str(settings.DATA_PATH.parent)

        try:
            # Check if this directory is a git repo
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=base_dir,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if res.returncode != 0:
                logger.debug("Directory is not a git repository. Skipping git sync.")
                return

           

            if not status_res.stdout.strip():
                logger.debug("No git changes to commit.")
                return

        

            pkt_tz = ZoneInfo("Asia/Karachi")
            now_pkt = datetime.now(pkt_tz).strftime("%Y-%m-%d %I:%M %p PKT")
            commit_msg = f"Auto-Sync: video summaries & daily index ({now_pkt})"

            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=base_dir,
                check=True,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            logger.info(f"Committed summaries to Git: '{commit_msg}'")

            # Check if remote origin exists
            remote_res = subprocess.run(
                ["git", "remote"],
                cwd=base_dir,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if "origin" in remote_res.stdout:
                # Push in background
                subprocess.Popen(
                    ["git", "push", "origin", "HEAD"],
                    cwd=base_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                logger.info("Initiated background git push to remote origin.")

        except Exception as e:
            logger.debug(f"Git auto-sync notice: {e}")
