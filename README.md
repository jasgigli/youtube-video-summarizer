# ⚡ YouTube Sub Summarizer — Pure Automated Backend Engine

An autonomous, headless YouTube digestion and executive summarization platform. 
No frontend or browser interaction required! Add channel handles to `channels.json`, and the automated engine checks for the latest published videos, synthesizes executive summaries via AI, and delivers them straight to your WhatsApp inbox without needing any clicks.

---

## 🚀 How to Use (Simple & Headless)

### 1. Configure Subscribed Channels in `channels.json`
Simply add YouTube channel handles or URLs into [channels.json](channels.json):
```json
{
  "channels": [
    "@awesome-coding",
    "@Fireship",
    "@lexfridman",
    "@veritasium",
    "@mkbhd",
    "@twominutepapers"
  ]
}
```

### 2. Run the Engine
Run the launcher from your terminal:
```bash
python run.py
```
Or to run with live log reloading:
```bash
python run.py --reload
```

### What Happens Automatically:
1. **Auto-Discovery:** On boot (and recurring on schedule), the backend reads `channels.json`.
2. **Channel Resolution:** Any newly added channels are auto-resolved and saved into the local database.
3. **Latest Video Fetching:** Checks each channel for the newest published video.
4. **AI Summarization:** Extracts the captions/overview and synthesizes a concise executive takeaway and actionable bullet points with Gemini AI.
5. **Direct WhatsApp Delivery:** Dispatches the summary straight to your WhatsApp inbox via the Twilio Cloud API — **zero manual clicks required!**

---

## 🧪 Running the Test Suite
The backend contains a self-contained test suite validating text sanitation, health endpoints, settings persistence, and offline AI synthesis:
```bash
python -m unittest discover -s backend/tests
```

---

## 🔌 API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health status |
| `GET` | `/api/channels` | List all tracked channels & video counters |
| `POST` | `/api/channels` | Add channel by URL, handle (`@creator`), or ID |
| `PATCH` | `/api/channels/{id}` | Toggle monitoring on/off |
| `DELETE` | `/api/channels/{id}` | Remove channel and cascade delete videos |
| `POST` | `/api/channels/{id}/sync` | Queue immediate scan for single channel |
| `GET` | `/api/videos` | Query videos with text search and status filters |
| `POST` | `/api/videos/{id}/summarize` | Queue video for transcript extraction and summary |
| `GET` | `/api/videos/{id}/transcript` | Get raw or cleaned transcript |
| `POST` | `/api/summaries/{id}/regenerate`| Re-synthesize with custom instruction lens |
| `GET` | `/api/summaries/{id}/export/markdown`| Download formatted summary as Markdown |
| `GET` | `/api/jobs` | View job execution history |
| `WS` | `/api/jobs/ws` | Live WebSocket streaming telemetry |
| `GET` | `/api/settings` | Retrieve active configurations (secrets masked) |
| `POST` | `/api/settings` | Update API credentials & scheduler intervals |
| `POST` | `/api/settings/test-connection` | Validate provider API credentials |
| `GET` | `/api/analytics` | High-level metrics (hours saved, topic trends) |
