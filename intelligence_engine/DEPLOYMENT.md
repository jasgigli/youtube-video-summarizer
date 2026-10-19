# 🚀 Free 24/7 Cloud Deployment Guide

This guide explains how to deploy this YouTube Sub Summarizer engine **100% free** so it runs 24 hours a day, 7 days a week in the cloud.

---

## 🏆 Recommended Free Cloud Providers

| Platform | Free Tier Highlights | Setup Time |
|---|---|---|
| **[Render.com](https://render.com)** *(Recommended)* | Free Web Service with Docker support, automatic Git deploys | ~3 minutes |
| **[Koyeb.com](https://koyeb.com)** | Free nano instance with $5 monthly credit, 24/7 uptime | ~3 minutes |
| **[Railway.app](https://railway.app)** | $5 monthly free trial credits, one-click deploy | ~2 minutes |

---

## 📋 Step 1: Push Code to a Private GitHub Repository

1. Go to [GitHub](https://github.com) and click **"New repository"**.
2. Name it (e.g. `youtube-video-summarizer`).
3. Set the repository to **Private** (recommended to keep your channel list private).
4. Run these commands in your project terminal:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git push -u origin main
   ```
   *(Note: Your `.env` and `.db` files are protected by `.gitignore` and will never be pushed publicly).*

---

## 🛠️ Step 2: Deploy on Render.com (100% Free)

1. Sign up / Log in to [Render.com](https://dashboard.render.com).
2. Click **New +** > **Web Service**.
3. Choose **Build and deploy from a Git repository** and connect your GitHub repo.
4. Render will auto-detect the configuration, or you can fill in:
   - **Name:** `youtube-sub-summarizer`
   - **Environment:** `Python` or `Docker`
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `python run.py --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free` ($0/mo)

5. Under **Environment Variables**, add the keys from your `.env`:
   - `GEMINI_API_KEY`: *(Your Google Gemini API Key)*
   - `TWILIO_ACCOUNT_SID`: *(Your Twilio Account SID from .env)*
   - `TWILIO_AUTH_TOKEN`: *(Your Twilio Auth Token from .env)*
   - `TWILIO_WHATSAPP_NUMBER`: `+14155238886`
   - `WHATSAPP_PHONE_NUMBER`: `923155619203`
   - `DEFAULT_PROVIDER`: `gemini`
   - `SYNC_INTERVAL_HOURS`: `4`

6. Click **Create Web Service**. Render will build and launch your application!

---

## ⏰ Step 3: Keeping the Free Service Awake 24/7

Free tier web services on Render go to sleep after 15 minutes of inactivity without inbound HTTP requests.
To keep your summarizer awake 24/7 without sleeping:

1. Copy your public service URL from Render (e.g., `https://youtube-sub-summarizer.onrender.com`).
2. Go to a free ping monitor like **[cron-job.org](https://cron-job.org)** or **[UptimeRobot](https://uptimerobot.com)**.
3. Create a free HTTP ping to:
   `https://your-service-name.onrender.com/api/health`
4. Set the interval to **every 10 minutes**.

> **Result:** Your service will never sleep! It will monitor [channels.json](channels.json), detect any newly published videos, generate clean summaries, and push them straight to your WhatsApp inbox at all hours.
