# 🌐 Tech & AI Omnichannel Intelligence & Content Aggregator

> **An automated intelligence engine that monitors, ingests, deduplicates, clusters, and summarizes developments across the global technology, software engineering, and AI ecosystem.**

---

## 🚀 Key Capabilities & Architecture

### 1. Omnichannel Ingestion Scope & Data Sources

- **Video Platforms:** Technology-company and creator YouTube channels configured in `feeds/youtube.json`, plus subscribed channels in [channels.json](channels.json) for explicit YouTube-only syncs.
- **Social & Community Forums:**
  - **Reddit:** `r/LocalLLaMA`, `r/MachineLearning`, `r/programming`, `r/artificial`, `r/technology` (captures post bodies, upvote signals, and top community commentary).
  - **Hacker News:** Front-page tech stories, technical critique, and developer sentiment via Algolia HN API.
  - **X & LinkedIn:** Official account/company posts through their authenticated APIs when the required credentials and organization identifiers are configured.
- **Direct Frontier AI Labs:** Official research publications and announcements from **OpenAI**, **Anthropic**, **Google DeepMind**, **Meta AI**, and **Hugging Face**.
- **Official Technology Companies:** Updates from **NVIDIA**, **Microsoft**, **Google**, **Apple**, and **AWS**.
- **Open Source & Code Repositories:** **GitHub Trending Repositories** (Daily trending frameworks, models, agent swarms, and libraries).
- **News & Engineering Blogs:** **TechCrunch AI**, **The Verge**, **Ars Technica**, **Wired Tech**, **MIT Technology Review**, **Dev.to**, and **Cloudflare Architecture**.
- **International Coverage:** Country-focused technology news aggregations across global regions, plus technology policy coverage.

### 2. Intelligent Processing Workflow

1. **Fetch & Enrich:** Reads enabled feeds in registry order, one at a time, uses source-specific API adapters, and extracts article text from configured RSS sources where available. An individual feed is skipped after a 20-second timeout or on failure; empty feeds are skipped immediately so later feeds still run.
2. **Deduplicate & Cluster:** Removes repeated items from the same source, groups corroborating reports while retaining separate source evidence, and keeps distinct developments about the same company separate.
3. **Key Information Extraction:** Summarizes one deduplicated topic at a time with the configured Gemini, OpenAI, Anthropic, or Ollama provider. Synthesis is bounded to 65 seconds per topic. If the provider is unavailable or times out, the engine writes a clearly labeled source-only report rather than inventing claims.
4. **Markdown Output:** Writes each topic report before advancing to the next topic, updating the index entry for that report rather than creating duplicate entries.
   - **Individual Topic Deep Dives (`.md`):** Formatted in `summaries/YYYY-MM-DD/[Topic_Title].md`.
   - **Consolidated Daily Briefing (`DAILY_BRIEF.md`):** Cross-source trend summary in `summaries/YYYY-MM-DD/DAILY_BRIEF.md`.

The scheduler runs the global omnichannel pipeline independently of the personal YouTube channel list. Reddit and Hacker News supply community signals. X sources require an official API bearer token (`X_BEARER_TOKEN`). LinkedIn sources require an authorized `LINKEDIN_ACCESS_TOKEN` and an `organization_id` on each feed; sources without credentials are explicitly skipped and logged.

---

## 🛠️ Usage & Commands

### 1. Configure Sources

- **Feeds Configuration:** Edit the categorized [feeds/](feeds/) JSON files and update `feeds/_index.json` when adding a new registry file.
- **YouTube Channels:** Edit [channels.json](channels.json) to add channel handles (e.g. `@Fireship`, `@lexfridman`).

### 2. Manual Immediate Ingestion

Run an on-demand sync from the command line:

```bash
# Ingest all omnichannel sources (Reddit, Hacker News, GitHub, Frontier Labs, Blogs)
python sync_now.py --mode omnichannel

# Ingest both subscribed YouTube channels AND all Omnichannel sources
python sync_now.py --mode all

# Ingest subscribed YouTube channels only
python sync_now.py --mode youtube
```

Or double-click [sync_now.bat](sync_now.bat) on Windows.

### 3. Run Autonomous Continuous Engine

To run the automated background server with scheduler and REST APIs:

```bash
python run.py
```

Or double-click [start_server.bat](start_server.bat).

Server will run at: `http://localhost:8000`  
Interactive Swagger API docs at: `http://localhost:8000/docs`

---

## 📁 Output Directory Layout

Each deduplicated development is stored as its own Markdown report. The global pipeline does not create social-post or audio output.

```
youtube_video-summarize_automation/
├── feeds/                    # Indexed, categorized omnichannel source registry
│   ├── _index.json
│   ├── ai_labs.json
│   ├── regional_news.json
│   └── ...
├── channels.json             # YouTube subscribed channels
├── summaries/
│   ├── INDEX.md              # Master library catalog of summaries
│   └── 2026-10-19/
│       ├── DAILY_BRIEF.md    # Consolidated Daily Omnichannel Intelligence Brief
│       ├── [One Markdown report per deduplicated development].md
│       └── ...
```

---

## 🔌 API Endpoints Reference

| Method | Endpoint                          | Description                                          |
| ------ | --------------------------------- | ---------------------------------------------------- |
| `POST` | `/api/omnichannel/sync`           | Trigger immediate Omnichannel intelligence ingestion |
| `GET`  | `/api/omnichannel/sources`        | List all configured data sources from the feed registry |
| `GET`  | `/api/omnichannel/recent-reports` | List recent generated Markdown reports and briefings |
| `GET`  | `/api/jobs`                       | View history of execution jobs and live logs         |
| `WS`   | `/api/jobs/ws`                    | Real-time WebSocket streaming telemetry              |
| `GET`  | `/api/summaries`                  | Query saved markdown summaries                       |
| `GET`  | `/api/channels`                   | View and manage subscribed YouTube channels          |
| `GET`  | `/api/settings`                   | Retrieve active LLM providers and configuration      |
