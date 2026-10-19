from src.app.routers.channels import router as channels_router
from src.app.routers.videos import router as videos_router
from src.app.routers.summaries import router as summaries_router
from src.app.routers.jobs import router as jobs_router
from src.app.routers.settings import router as settings_router
from src.app.routers.analytics import router as analytics_router
from src.app.routers.omnichannel import router as omnichannel_router
from src.app.routers.saas import router as saas_router
from src.app.routers.b2b import router as b2b_router
from src.app.routers.workspace import router as workspace_router
from src.app.routers.crawlers import router as crawlers_router
from src.app.routers.newsletter import router as newsletter_router

__all__ = [
    "channels_router",
    "videos_router",
    "summaries_router",
    "jobs_router",
    "settings_router",
    "analytics_router",
    "omnichannel_router",
    "saas_router",
    "b2b_router",
    "workspace_router",
    "crawlers_router",
    "newsletter_router"
]
