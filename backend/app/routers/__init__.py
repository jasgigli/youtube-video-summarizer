from backend.app.routers.channels import router as channels_router
from backend.app.routers.videos import router as videos_router
from backend.app.routers.summaries import router as summaries_router
from backend.app.routers.jobs import router as jobs_router
from backend.app.routers.settings import router as settings_router
from backend.app.routers.analytics import router as analytics_router

__all__ = [
    "channels_router",
    "videos_router",
    "summaries_router",
    "jobs_router",
    "settings_router",
    "analytics_router"
]
