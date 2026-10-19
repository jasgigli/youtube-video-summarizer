"""
run.py — Starts the Intelligence Engine as a background server with
scheduler, REST APIs, and WebSocket streaming.

Usage:
    python run.py
"""

import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `src.app.*` imports resolve.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env before importing anything that reads settings.
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import uvicorn
from src.app.config import settings


def main():
    uvicorn.run(
        "src.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
