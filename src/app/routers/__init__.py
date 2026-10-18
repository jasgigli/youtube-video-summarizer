from src.app.routers.channels import router as channels_router
from src.app.routers.videos import router as videos_router
from src.app.routers.summaries import router as summaries_router
from src.app.routers.jobs import router as jobs_router
from src.app.routers.settings import router as settings_router
from src.app.routers.analytics import router as analytics_router

__all__ = [
    "channels_router",
    "videos_router",
    "summaries_router",
    "jobs_router",
    "settings_router",
    "analytics_router"
]
