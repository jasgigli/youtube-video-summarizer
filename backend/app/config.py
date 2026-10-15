import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings

# Root directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "YouTube Sub Summarizer"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Storage
    DATA_PATH: Path = DATA_DIR
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
    DEFAULT_MODEL_GEMINI: str = "gemini-flash-lite-latest"
    DEFAULT_MODEL_OPENAI: str = "gpt-4o-mini"
    DEFAULT_MODEL_ANTHROPIC: str = "claude-3-5-haiku-20241022"
    DEFAULT_MODEL_OLLAMA: str = "llama3.2"
    
    # Automation & Scheduler
    ENABLE_SCHEDULER: bool = True
    SYNC_INTERVAL_HOURS: int = 6
    WHATSAPP_PHONE_NUMBER: str = "923155619203"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "+14155238886"
    
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
