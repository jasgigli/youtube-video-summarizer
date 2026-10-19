import os
import shutil
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from src.app.config import settings
from src.app.utils.logger import logger

class ArchiveService:
    """
    Weekly Summary Archive and Housekeeping Engine.
    Archives daily summary folders older than ARCHIVE_AFTER_DAYS (default 14 days)
    into compressed ZIP files inside summaries/archive/YYYY-MM.zip to keep workspace lean.
    """

    @classmethod
    def run_cleanup(cls):
        """Finds old summary folders and archives them into monthly zip archives."""
        summaries_dir = settings.SUMMARIES_PATH
        if not summaries_dir.exists():
            return

        archive_dir = summaries_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        cutoff_date = datetime.now() - timedelta(days=getattr(settings, "ARCHIVE_AFTER_DAYS", 14))
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        archived_count = 0
        for folder in summaries_dir.iterdir():
            if folder.is_dir() and folder.name != "archive":
                # Check if matches YYYY-MM-DD
                if len(folder.name) == 10 and folder.name < cutoff_str:
                    try:
                        month_str = folder.name[:7]  # YYYY-MM
                        zip_path = archive_dir / f"{month_str}.zip"

                        with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zipf:
                            for file in folder.rglob("*"):
                                arcname = f"{folder.name}/{file.relative_to(folder)}"
                                zipf.write(file, arcname)

                        # Safely remove old folder
                        shutil.rmtree(folder)
                        archived_count += 1
                        logger.info(f"Archived old summary folder {folder.name} to {zip_path.name}")
                    except Exception as e:
                        logger.warning(f"Could not archive {folder.name}: {e}")

        if archived_count > 0:
            logger.info(f"Weekly archive cleanup complete. Archived {archived_count} folders.")
