import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings

# Root directory resolution
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Check if data exists in workspace root (parent) or locally
if (BASE_DIR.parent / "data" / "app.db").exists():
    DATA_DIR = BASE_DIR.parent / "data"
    WORKSPACE_ROOT = BASE_DIR.parent
else:
    DATA_DIR = BASE_DIR / "data"
    WORKSPACE_ROOT = BASE_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)

SUMMARIES_DIR = WORKSPACE_ROOT / "summaries" if (WORKSPACE_ROOT / "summaries").exists() else BASE_DIR / "summaries"
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

# Feeds directory — prefer workspace-level feeds/, fall back to src-level
FEEDS_DIR = WORKSPACE_ROOT / "feeds" if (WORKSPACE_ROOT / "feeds").exists() else BASE_DIR / "feeds"


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment and .env file."""

    APP_NAME: str = "Tech & AI Omnichannel Intelligence Engine"
    VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Paths
    DATA_PATH: Path = DATA_DIR
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'app.db'}"
    SUMMARIES_PATH: Path = SUMMARIES_DIR

    # YouTube Configuration
    YOUTUBE_API_KEY: str = ""
    MAX_VIDEOS_PER_CHANNEL_SYNC: int = 1
    REQUEST_TIMEOUT_SECONDS: int = 15

    # LLM Settings
    DEFAULT_PROVIDER: str = "gemini"  # "gemini" | "openai" | "anthropic" | "ollama" | "mock"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    X_BEARER_TOKEN: str = ""
    LINKEDIN_ACCESS_TOKEN: str = ""
    LINKEDIN_API_VERSION: str = "202601"
    DEFAULT_MODEL_GEMINI: str = "gemini-flash-latest"
    DEFAULT_MODEL_OPENAI: str = "gpt-4o-mini"
    DEFAULT_MODEL_ANTHROPIC: str = "claude-3-5-haiku-20241022"
    DEFAULT_MODEL_OLLAMA: str = "llama3.2"

    # Automation & Scheduler
    ENABLE_SCHEDULER: bool = True
    SYNC_INTERVAL_HOURS: int = 2  # Checks every 2 hours

    # Advanced Content Filters
    FILTER_OUT_SHORTS: bool = True
    FILTER_OUT_LIVE_STREAMS: bool = True

    # Global Tech Feeds & News Monitoring
    ENABLE_MULTI_SOURCE_MONITORING: bool = True
    FEEDS_CONFIG_PATH: Path = FEEDS_DIR

    # SaaS 4-Tier Pricing & Limits
    TIER_FREE_PRICE: float = 0.0
    TIER_FREE_DAILY_SOCIAL_COPIES: int = 3
    TIER_FREE_DAILY_SUMMARIES_LIMIT: int = 5

    TIER_PRO_MONTHLY_PRICE: float = 5.0
    TIER_PRO_YEARLY_PRICE: float = 49.0

    TIER_TEAM_MONTHLY_PRICE: float = 19.0
    TIER_TEAM_INCLUDED_SEATS: int = 5
    TIER_TEAM_EXTRA_SEAT_PRICE: float = 3.0

    TIER_B2B_MONTHLY_PRICE: float = 29.0
    TIER_B2B_METERED_PER_REQ_PRICE: float = 0.005
    TIER_B2B_DEFAULT_RATE_LIMIT_PER_MIN: int = 60

    ARCHIVE_AFTER_DAYS: int = 14

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()
