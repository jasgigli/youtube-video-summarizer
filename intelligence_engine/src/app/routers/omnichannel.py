import re
from fastapi import APIRouter, HTTPException, Query
from src.app.config import settings
from src.app.services.job_service import JobService
from src.app.services.feed_registry_service import FeedRegistryService

router = APIRouter(prefix="/omnichannel", tags=["Omnichannel Intelligence"])

@router.post("/sync")
async def trigger_omnichannel_sync():
    """Triggers an immediate Omnichannel multi-source intelligence ingestion and synthesis pipeline."""
    job_uuid = await JobService.create_and_run_job("SYNC_OMNICHANNEL")
    return {
        "message": "Omnichannel Intelligence pipeline triggered successfully",
        "job_uuid": job_uuid,
        "platforms_monitored": [
            "YouTube", "Reddit", "Hacker News", "GitHub", "X", "LinkedIn",
            "Official Company Sites", "International News", "Research Feeds", "Tech Blogs"
        ]
    }

@router.get("/sources")
def list_omnichannel_sources():
    """Lists all configured data sources from the indexed feed registry."""
    feeds_path = settings.FEEDS_CONFIG_PATH
    try:
        data = FeedRegistryService.load_feeds(feeds_path)
        return {"count": len(data), "sources": data}
    except FileNotFoundError:
        return {"sources": [], "count": 0}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read feed registry at {feeds_path}: {str(e)}"
        )

@router.get("/recent-reports")
def list_recent_reports(limit: int = Query(20, ge=1, le=100)):
    """Retrieves recent omnichannel reports and markdown intelligence files."""
    summaries_dir = settings.SUMMARIES_PATH
    reports = []
    if not summaries_dir.exists():
        return {"reports": [], "count": 0}

    for folder in sorted(summaries_dir.iterdir(), reverse=True):
        if folder.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", folder.name):
            for md_file in sorted(folder.glob("*.md"), reverse=True):
                content = md_file.read_text(encoding="utf-8", errors="replace")
                reports.append({
                    "date": folder.name,
                    "filename": md_file.name,
                    "title": md_file.stem,
                    "is_daily_brief": md_file.name == "DAILY_BRIEF.md",
                    "preview": content[:300]
                })
                if len(reports) >= limit:
                    break
        if len(reports) >= limit:
            break

    return {
        "count": len(reports),
        "reports": reports
    }
