import json
import time
import httpx
import re
from typing import Dict, Any, Optional, List
from src.app.config import settings
from src.app.utils.logger import logger
from src.app.utils.text_cleaner import estimate_tokens

SYSTEM_PROMPT = """You are an elite technology analyst and executive summarizer.
Your goal is to transform YouTube video content into SHORT, CONCISE, HIGH-SIGNAL Markdown summaries that can be read in under 90 seconds.

CORE DIRECTIVE - MAXIMUM BREVITY & HIGH SIGNAL:
- Be concise, direct, and scannable. Avoid fluff, filler words, and long winded explanations.
- Keep paragraphs short (2-3 sentences max). Use bullet points wherever possible.
- Still maintain category-specific intelligence (AI news vs roadmaps vs tech updates vs software releases vs FAANG vs tutorials).

Identify which category best matches:
1. "ai_news": AI breakthroughs, LLM frontier models (OpenAI, Anthropic, Gemini, DeepSeek), AI agent frameworks, benchmarks, AI hardware.
2. "tech_updates": Programming language releases, web frameworks (React, Next.js, Node, Python, Rust, Go), API deprecations, breaking changes.
3. "roadmap_career": Career advice, developer roadmaps, learning tracks, interview prep, skill ladders.
4. "software_releases": New developer tools, open-source repositories, CLI utilities, databases, IDE extensions.
5. "industry_faang": Tech giants (Google, Apple, Microsoft, Meta, Amazon, NVIDIA), corporate strategy, layoffs, tech economics, acquisitions.
6. "tutorials_deepdives": Technical how-to guides, architecture blueprints, system design, coding walkthroughs.
7. "general_tech": Industry commentary, developer debates, productivity tips, technology culture.

JSON OUTPUT STRUCTURE:
Output MUST strictly be raw valid JSON matching this schema:
{
  "category": "ai_news | tech_updates | roadmap_career | software_releases | industry_faang | tutorials_deepdives | general_tech",
  "category_display": "Human-friendly label with emoji (e.g. '🤖 AI News', '🗺️ Developer Roadmap', '🚀 Tech Update', '🛠️ Dev Tools', '🏢 Big Tech / FAANG', '💻 Deep Dive', '💡 Tech Insight')",
  "one_sentence_takeaway": "A single, punchy sentence capturing the core message and why it matters.",
  "context_and_overview": "Exactly 1 short paragraph (2-3 sentences max) explaining what this video covers and why it is important.",
  "key_takeaways": [
    "**Key Point 1:** 1-2 sentence concise explanation.",
    "**Key Point 2:** 1-2 sentence concise explanation.",
    "**Key Point 3:** 1-2 sentence concise explanation."
  ],
  "detailed_breakdown": "A compact Markdown section tailored to the video's category. Each subheading should have only 2-3 short bullet points (1-2 sentences each). See guidelines below.",
  "action_items": [
    "Practical step or takeaway 1.",
    "Practical step or takeaway 2."
  ],
  "notable_quotes": [
    {"quote": "One key quote or stat (under 25 words)", "context_or_timestamp": "Context"}
  ],
  "topics": ["Tag1", "Tag2", "Tag3"],
  "sentiment": "informative | bullish | cautious | instructional | analytical"
}

CATEGORY-SPECIFIC BREAKDOWN FORMATS (Keep each section to 2-3 brief bullets!):
- For "ai_news":
  ### 🔬 Model & Specs
  - Bullet 1
  - Bullet 2
  ### ⚡ Capabilities & Impact
  - Bullet 1
  - Bullet 2
  ### 🔓 Access & Availability
  - Bullet 1

- For "tech_updates":
  ### 📦 What's New
  - Bullet 1
  - Bullet 2
  ### ⚠️ Breaking Changes & Upgrading
  - Bullet 1
  - Bullet 2

- For "roadmap_career":
  ### 🎯 Target & Prerequisites
  - Bullet 1
  ### 🪜 Core Learning Path
  - Bullet 1 (Stage 1)
  - Bullet 2 (Stage 2)
  ### 🔨 Recommended Practice
  - Bullet 1

- For "software_releases":
  ### 💡 Problem Solved
  - Bullet 1
  ### ⚙️ Core Features & Differentiators
  - Bullet 1
  - Bullet 2
  ### ⚖️ Verdict (Pros & Cons)
  - Bullet 1

- For "industry_faang":
  ### 📰 The Core Event
  - Bullet 1
  - Bullet 2
  ### ♟️ Strategic Motivation & Developer Impact
  - Bullet 1
  - Bullet 2

- For "tutorials_deepdives":
  ### 📐 Problem & Architecture
  - Bullet 1
  ### 🛠️ Key Implementation Steps
  - Bullet 1
  - Bullet 2
  ### 🛡️ Production Gotchas
  - Bullet 1

- For "general_tech":
  ### 🎙️ Core Thesis
  - Bullet 1
  - Bullet 2
  ### 🏁 The Bottom Line
  - Bullet 1
  - Bullet 2

Rules:
1. Keep the whole output tight and easy to skim in 60-90 seconds.
2. NEVER write long walls of text. Use bullet points and bold headers.
3. Return raw valid JSON ONLY without ```json markdown fences.
"""

class LLMService:
    """
    Unified multi-provider LLM orchestrator.
    Dispatches prompts to Google Gemini, OpenAI, Anthropic Claude, Ollama,
    or a rich offline mock engine with category-adaptive intelligence.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.provider = (provider or settings.DEFAULT_PROVIDER).lower()
        self.api_key = api_key
        self.model_name = model_name

    async def summarize_video(
        self,
        title: str,
        channel_name: str,
        transcript: str,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a structured, category-adaptive summary from video title and transcript.
        Includes timing, token count, and resilient fallbacks.
        """
        start_time = time.time()
        transcript_str = (transcript or "").strip()
        transcript_snippet = transcript_str[:60000]

        user_content = (
            f"Video Title: {title}\n"
            f"Channel: {channel_name}\n\n"
            f"Transcript / Description Content:\n{transcript_snippet}\n\n"
        )
        if custom_instructions:
            user_content += f"Special Focus / Instructions: {custom_instructions}\n"

        try:
            if self.provider == "gemini":
                result = await self._call_gemini(user_content)
            elif self.provider == "openai":
                result = await self._call_openai(user_content)
            elif self.provider == "anthropic":
                result = await self._call_anthropic(user_content)
            elif self.provider == "ollama":
                result = await self._call_ollama(user_content)
            else:
                result = await self._mock_summary(title, channel_name, transcript)
        except Exception as e:
            logger.error(f"Provider {self.provider} failed: {e}. Falling back to structured synthesis.")
            result = await self._mock_summary(title, channel_name, transcript, error_context=str(e))

        elapsed = round(time.time() - start_time, 2)
        result["processing_time_sec"] = elapsed
        result["tokens_used"] = estimate_tokens(transcript_snippet)
        result["provider"] = self.provider
        result["model_name"] = self.model_name or self._default_model_for_provider()

        # Ensure required fields exist
        if "category" not in result:
            result["category"] = self._detect_category_heuristic(title, transcript)
        if "category_display" not in result:
            result["category_display"] = self._format_category_display(result["category"])
        if "context_and_overview" not in result:
            result["context_and_overview"] = result.get("detailed_breakdown", "")[:350]

        return result

    def _default_model_for_provider(self) -> str:
        if self.provider == "gemini":
            return settings.DEFAULT_MODEL_GEMINI
        if self.provider == "openai":
            return settings.DEFAULT_MODEL_OPENAI
        if self.provider == "anthropic":
            return settings.DEFAULT_MODEL_ANTHROPIC
        if self.provider == "ollama":
            return settings.DEFAULT_MODEL_OLLAMA
        return "offline-synthesizer"

    async def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        """Direct REST call to Google Gemini API with automatic model fallback."""
        key = self.api_key or settings.GEMINI_API_KEY
        if not key:
            raise ValueError("Gemini API key is not configured. Set it in Settings or .env.")

        primary_model = self.model_name or settings.DEFAULT_MODEL_GEMINI
        models_to_try = [primary_model, "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-pro-latest"]
        unique_models = list(dict.fromkeys(models_to_try))

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{SYSTEM_PROMPT}\n\n{prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.25,
                "responseMimeType": "application/json"
            }
        }

        last_error = None
        async with httpx.AsyncClient(timeout=45.0) as client:
            for model_candidate in unique_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_candidate}:generateContent?key={key}"
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                            self.model_name = model_candidate
                            return self._parse_json_response(raw_text)
                    elif resp.status_code in (503, 404, 429):
                        logger.warning(f"Gemini model {model_candidate} returned HTTP {resp.status_code}, trying next model candidate...")
                        last_error = resp.text
                        continue
                    else:
                        raise RuntimeError(f"Gemini API returned HTTP {resp.status_code}: {resp.text}")
                except Exception as ex:
                    last_error = str(ex)
                    logger.warning(f"Attempt with model {model_candidate} failed: {ex}")

        raise RuntimeError(f"All Gemini models exhausted. Last error: {last_error}")

    async def _call_openai(self, prompt: str) -> Dict[str, Any]:
        key = self.api_key or settings.OPENAI_API_KEY
        if not key:
            raise ValueError("OpenAI API key is not configured.")

        model = self.model_name or settings.DEFAULT_MODEL_OPENAI
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API returned HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return self._parse_json_response(raw_text)

    async def _call_anthropic(self, prompt: str) -> Dict[str, Any]:
        key = self.api_key or settings.ANTHROPIC_API_KEY
        if not key:
            raise ValueError("Anthropic API key is not configured.")

        model = self.model_name or settings.DEFAULT_MODEL_ANTHROPIC
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Anthropic API returned HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            raw_text = data["content"][0]["text"]
            return self._parse_json_response(raw_text)

    async def _call_ollama(self, prompt: str) -> Dict[str, Any]:
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        model = self.model_name or settings.DEFAULT_MODEL_OLLAMA
        url = f"{base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": f"{SYSTEM_PROMPT}\n\nUser Content:\n{prompt}",
            "stream": False,
            "format": "json"
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            raw_text = data.get("response", "{}")
            return self._parse_json_response(raw_text)

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Cleans and extracts JSON payload from model response."""
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        return json.loads(clean)

    def _detect_category_heuristic(self, title: str, transcript: str) -> str:
        """Heuristic category detection fallback."""
        text = f"{title} {transcript[:2000]}".lower()
        if any(w in text for w in ["roadmap", "career", "become a", "learning path", "salary", "interview"]):
            return "roadmap_career"
        if any(w in text for w in ["gpt", "claude", "gemini", "deepseek", "llm", "artificial intelligence", "openai", "agentic", "ai news", "neural", "diffusion"]):
            return "ai_news"
        if any(w in text for w in ["v1.", "v2.", "v3.", "release", "released", "what's new", "upgrade", "react 19", "next.js 15", "python 3."]):
            return "tech_updates"
        if any(w in text for w in ["google", "meta", "microsoft", "apple", "amazon", "nvidia", "layoffs", "antitrust", "faang"]):
            return "industry_faang"
        if any(w in text for w in ["tool", "open source", "github repo", "terminal", "cli", "extension", "plugin", "database"]):
            return "software_releases"
        if any(w in text for w in ["build a", "how to build", "tutorial", "crash course", "step by step", "system design", "architecture"]):
            return "tutorials_deepdives"
        return "general_tech"

    def _format_category_display(self, category: str) -> str:
        mapping = {
            "ai_news": "🤖 AI News & Breakthroughs",
            "tech_updates": "🚀 Tech Updates & Frameworks",
            "roadmap_career": "🗺️ Career Roadmap & Learning Path",
            "software_releases": "🛠️ Software Release & Dev Tools",
            "industry_faang": "🏢 Tech Giants & FAANG Industry",
            "tutorials_deepdives": "💻 Code Tutorial & Deep Dive",
            "general_tech": "💡 Tech Analysis & Opinion"
        }
        return mapping.get(category, "💡 Tech Analysis & Opinion")

    async def _mock_summary(
        self,
        title: str,
        channel_name: str,
        transcript: str,
        error_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Offline synthesizer with category support."""
        category = self._detect_category_heuristic(title, transcript)
        cat_display = self._format_category_display(category)
        paragraphs = [p.strip() for p in transcript.split("\n\n") if len(p.strip()) > 30]
        first_p = paragraphs[0] if paragraphs else "Overview based on video metadata."

        note_prefix = f"*(Generated via Offline Synthesizer: {error_context})*\n\n" if error_context else ""

        return {
            "category": category,
            "category_display": cat_display,
            "one_sentence_takeaway": f"In '{title}', {channel_name} presents key developments, critical considerations, and actionable insights.",
            "context_and_overview": (
                f"{channel_name} addresses important recent trends and developments in this video. "
                f"The topic explores core architectural concepts and practical nuances that developers need to consider today."
            ),
            "key_takeaways": [
                f"**Core Announcement / Thesis:** The video explores central dynamics introduced in '{title}'.",
                f"**Contextual Significance:** {channel_name} highlights practical implications, tradeoffs, and structural shifts.",
                "**Methodology & Execution:** Emphasis on measurable outcomes, systematic approaches, and real-world testing.",
                "**Long-term Trajectory:** Key takeaways for practitioners looking to adapt their workflows."
            ],
            "detailed_breakdown": (
                f"{note_prefix}## Overview & Context\n"
                f"{channel_name} breaks down the fundamentals of the subject matter, "
                f"walking through historical context and emerging developments.\n\n"
                f"## Core Concepts & Analysis\n"
                f"- **Foundational Mechanism:** {first_p[:200]}...\n"
                f"- **Key Trade-offs:** Detailed analysis of constraints and strategic options.\n"
                f"- **Real-World Application:** How to translate these insights into concrete decisions.\n\n"
                f"## Synthesis & Takeaway\n"
                f"A structured overview covering primary considerations and practical advice."
            ),
            "action_items": [
                f"Review the primary recommendations outlined by {channel_name}.",
                "Benchmark your current approach against the framework discussed in the video.",
                "Implement key findings into your ongoing workflow."
            ],
            "notable_quotes": [
                {"quote": f"Insightful perspective shared by {channel_name}.", "context_or_timestamp": "[Overview]"}
            ],
            "topics": [category.replace("_", " ").title(), channel_name, "Technology"],
            "sentiment": "analytical"
        }
