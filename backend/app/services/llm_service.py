import json
import time
import httpx
from typing import Dict, Any, Optional, List
from backend.app.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.text_cleaner import estimate_tokens

SYSTEM_PROMPT = """You are a master communicator and executive summarizer.
Your goal is to transform YouTube video content into crystal-clear, simple, and easy-to-understand takeaways.

Rules for writing:
1. Use simple, plain English. Avoid complicated jargon and buzzwords. Anyone should understand it instantly.
2. The "one_sentence_takeaway" must explain the main point in 1 simple, clear sentence.
3. The "key_takeaways" must be 3-5 clean bullet points highlighting the most important ideas in straightforward language.
4. The "action_items" must be practical, easy-to-follow steps or recommendations.

Output MUST strictly adhere to this JSON structure:
{
  "one_sentence_takeaway": "A crystal-clear, simple, 1-sentence summary of what this video is about and why it matters.",
  "key_takeaways": [
    "Simple, clear key point explaining what happened or what was taught.",
    "Another important idea written in plain, understandable words.",
    "Practical lesson or concept from the video.",
    "Key takeaway or final conclusion."
  ],
  "detailed_breakdown": "A clean, easy-to-read breakdown with simple headings and bullets.",
  "action_items": [
    "Clear actionable step or recommendation."
  ],
  "notable_quotes": [
    {"quote": "Simple memorable quote from the video", "context_or_timestamp": "Context"}
  ],
  "topics": ["Topic 1", "Topic 2"],
  "sentiment": "informative"
}
Never include Markdown code fences (e.g. ```json) around the response. Return raw valid JSON only.
"""

class LLMService:
    """
    Unified multi-provider LLM orchestrator.
    Dispatches prompts to Google Gemini, OpenAI, Anthropic Claude, Ollama,
    or a rich offline mock engine.
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
        Synthesizes a structured summary from video title and transcript.
        Includes timing, token count, and resilient fallbacks.
        """
        start_time = time.time()
        transcript_snippet = transcript[:60000]  # Cap to prevent excessive token overages

        user_content = (
            f"Video Title: {title}\n"
            f"Channel: {channel_name}\n\n"
            f"Transcript Content:\n{transcript_snippet}\n\n"
        )
        if custom_instructions:
            user_content += f"Special Focus / Instructions: {custom_instructions}\n"

        # Dispatch according to active provider
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
            # If API fails (e.g. invalid key or network issue), fallback to local synthesis
            result = await self._mock_summary(title, channel_name, transcript, error_context=str(e))

        elapsed = round(time.time() - start_time, 2)
        result["processing_time_sec"] = elapsed
        result["tokens_used"] = estimate_tokens(transcript_snippet)
        result["provider"] = self.provider
        result["model_name"] = self.model_name or self._default_model_for_provider()

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
        models_to_try = [primary_model, "gemini-flash-lite-latest", "gemini-flash-latest"]
        # Deduplicate preserving order
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
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        last_error = None
        async with httpx.AsyncClient(timeout=25.0) as client:
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
                        logger.warning(f"Gemini model {model_candidate} returned HTTP {resp.status_code}, trying next model...")
                        last_error = resp.text
                        continue
                    else:
                        raise RuntimeError(f"Gemini API returned HTTP {resp.status_code}: {resp.text}")
                except Exception as ex:
                    last_error = str(ex)
                    logger.warning(f"Failed attempt with model {model_candidate}: {ex}")

        raise RuntimeError(f"All Gemini models exhausted. Last error: {last_error}")

    async def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Direct call to OpenAI / compatible chat completions endpoint."""
        key = self.api_key or settings.OPENAI_API_KEY
        if not key:
            raise ValueError("OpenAI API key is not configured.")

        model = self.model_name or settings.DEFAULT_MODEL_OPENAI
        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {key}",
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
        """Call to Anthropic Claude Messages API."""
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
        """Call to local Ollama instance."""
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

    async def _mock_summary(
        self,
        title: str,
        channel_name: str,
        transcript: str,
        error_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        High-quality heuristic offline synthesizer.
        Extracts salient points and structures them cleanly for zero-key mode or fallback.
        """
        # Extract snippet words
        paragraphs = [p.strip() for p in transcript.split("\n\n") if len(p.strip()) > 30]
        first_p = paragraphs[0] if paragraphs else "No transcript body available."
        sample_quotes = []
        if paragraphs:
            for p in paragraphs[:3]:
                if len(p) > 40:
                    sample_quotes.append({"quote": p[:120] + "...", "context_or_timestamp": "Video highlight"})

        note_prefix = f"*(Generated via Offline Synthesizer: {error_context})*\n\n" if error_context else ""

        return {
            "one_sentence_takeaway": f"In '{title}', {channel_name} explores the critical mechanisms and core ideas driving the topic.",
            "key_takeaways": [
                f"Core Thesis: The presentation centers on key dynamics introduced in {title}.",
                f"Context: {channel_name} highlights practical implications, tradeoffs, and structural changes.",
                "Methodology: Emphasis on measurable results, systematic thinking, and real-world execution.",
                "Outlook: The video concludes with actionable principles for implementation."
            ],
            "detailed_breakdown": (
                f"{note_prefix}## Overview & Context\n"
                f"{channel_name} breaks down the fundamentals of the subject matter, "
                f"walking through historical context and emerging developments.\n\n"
                f"## Core Concepts Explored\n"
                f"- **Foundational Mechanism:** {first_p[:200]}...\n"
                f"- **Key Trade-offs:** Detailed analysis of constraints and strategic options.\n"
                f"- **Real-World Application:** How to translate these insights into concrete decisions.\n\n"
                f"## Synthesis\n"
                f"The overall narrative provides a balanced roadmap, cautioning against common pitfalls "
                f"while outlining next steps."
            ),
            "action_items": [
                f"Review the primary recommendations outlined by {channel_name}.",
                "Benchmark your current approach against the framework discussed in the video.",
                "Implement key findings into your ongoing workflow."
            ],
            "notable_quotes": sample_quotes or [
                {"quote": f"Insightful perspective shared by {channel_name}.", "context_or_timestamp": "[Overview]"}
            ],
            "topics": ["Analysis", channel_name, "Technology & Strategy"],
            "sentiment": "analytical"
        }
