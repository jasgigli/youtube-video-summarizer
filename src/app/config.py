import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings

# Root directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SUMMARIES_DIR = BASE_DIR / "summaries"
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

SOCIAL_POSTS_DIR = BASE_DIR / "social_posts"
SOCIAL_POSTS_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "YouTube Sub Summarizer"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    
    # Storage
    DATA_PATH: Path = DATA_DIR
    SUMMARIES_PATH: Path = SUMMARIES_DIR
    SOCIAL_POSTS_PATH: Path = SOCIAL_POSTS_DIR
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'app.db'}"
    
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
    
    # Social Media Content Generation & Notifications
    ENABLE_AUDIO_PODCAST: bool = False
    ENABLE_SOCIAL_POST_EXPORT: bool = True
    ENABLE_DESKTOP_NOTIFICATIONS: bool = True
    ENABLE_AUTO_GIT_SYNC: bool = True
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
