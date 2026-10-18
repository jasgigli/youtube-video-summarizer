import unittest
import asyncio
from fastapi.testclient import TestClient
from src.app.main import app
from src.app.utils.text_cleaner import clean_transcript_text, estimate_tokens
from src.app.services.llm_service import LLMService

class TestYouTubeSummarizerBackend(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("YouTube Sub Summarizer", data["app"])

    def test_text_cleaner(self):
        raw = "Hello world [Music] this is a test. (Applause)    Multiple   spaces should be fixed."
        cleaned = clean_transcript_text(raw)
        self.assertNotIn("[Music]", cleaned)
        self.assertNotIn("(Applause)", cleaned)
        self.assertNotIn("   ", cleaned)
        self.assertGreater(estimate_tokens(cleaned), 0)

    def test_offline_llm_synthesis(self):
        llm = LLMService(provider="mock")
        summary = asyncio.run(llm.summarize_video(
            title="Test Artificial Intelligence",
            channel_name="Tech Channel",
            transcript="Artificial intelligence is transforming automation and developer productivity."
        ))
        self.assertIn("one_sentence_takeaway", summary)
        self.assertGreater(len(summary["key_takeaways"]), 0)
        self.assertIn("detailed_breakdown", summary)
        self.assertGreater(len(summary["action_items"]), 0)
        self.assertEqual(summary["provider"], "mock")

    def test_settings_endpoint(self):
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("default_provider", data)
        self.assertIn("max_videos_per_channel", data)

    def test_analytics_endpoint(self):
        response = self.client.get("/api/analytics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_channels", data)
        self.assertIn("hours_saved", data)

if __name__ == "__main__":
    unittest.main()
