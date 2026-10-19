#!/usr/bin/env python3
"""
Tech & AI Omnichannel Intelligence & Content Aggregator — Server & Engine.
Continuously monitors YouTube, Reddit, Hacker News, GitHub, Frontier AI Labs,
and Engineering Blogs, clusters cross-platform trends, and generates Markdown reports.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

def check_dependencies():
    """Verify required Python packages are available."""
    required = ["fastapi", "uvicorn", "sqlalchemy", "feedparser", "httpx", "pydantic"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[!] Missing required Python packages: {', '.join(missing)}")
        print("[!] Install them with: pip install -r src/requirements.txt")
        sys.exit(1)

def main():
    default_port = int(os.environ.get("PORT", 8000))
    default_host = os.environ.get("HOST", "0.0.0.0") if os.environ.get("PORT") else "127.0.0.1"
    parser = argparse.ArgumentParser(description="Launch Tech & AI Omnichannel Intelligence Engine")
    parser.add_argument("--host", default=default_host, help=f"Host binding (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port binding (default: {default_port})")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload for development")
    args = parser.parse_args()

    check_dependencies()

    print("=" * 70)
    print("  >> Tech & AI Omnichannel Intelligence & Content Aggregator <<")
    print(f"  Feeds Config:    {ROOT_DIR / 'feeds'}")
    print(f"  Channels Config: {ROOT_DIR / 'channels.json'}")
    print(f"  Server URL:      http://{args.host}:{args.port}")
    print(f"  API Docs:        http://{args.host}:{args.port}/docs")
    print("=" * 70)

    import uvicorn
    uvicorn.run(
        "src.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(ROOT_DIR)
    )

if __name__ == "__main__":
    main()
