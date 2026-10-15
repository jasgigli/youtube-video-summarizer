#!/usr/bin/env python3
"""
YouTube Sub Summarizer — Headless Automated Engine
Runs the backend pipeline, checks channels.json for subscribed channels,
fetches the newest published videos, summarizes them with AI, and sends
them directly to your WhatsApp inbox via Twilio Cloud.
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

def check_dependencies():
    """Verify required Python packages are available."""
    required = ["fastapi", "uvicorn", "sqlalchemy", "feedparser", "youtube_transcript_api", "pydantic_settings", "twilio"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[!] Missing required Python packages: {', '.join(missing)}")
        print("[!] Install them with: pip install -r backend/requirements.txt twilio")
        sys.exit(1)

def main():
    default_port = int(os.environ.get("PORT", 8000))
    default_host = os.environ.get("HOST", "0.0.0.0") if os.environ.get("PORT") else "127.0.0.1"
    parser = argparse.ArgumentParser(description="Launch YouTube Sub Summarizer (Headless Engine)")
    parser.add_argument("--host", default=default_host, help=f"Host binding (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port binding (default: {default_port})")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload for development")
    parser.add_argument("--sync-now", action="store_true", help="Run sync immediately on startup")
    args = parser.parse_args()

    check_dependencies()

    print("=" * 65)
    print("  >> YouTube Sub Summarizer - Pure Automated Backend Engine <<")
    print(f"  Channels Config: {ROOT_DIR / 'channels.json'}")
    print(f"  Server URL:      http://{args.host}:{args.port}")
    print(f"  API Docs:        http://{args.host}:{args.port}/docs")
    print("=" * 65)

    import uvicorn
    # Pass app_dir so uvicorn reloader sub-processes always find 'backend'
    uvicorn.run(
        "backend.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(ROOT_DIR)
    )

if __name__ == "__main__":
    main()

