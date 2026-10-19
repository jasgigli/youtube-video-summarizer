import unittest
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from src.app.config import settings
from src.app.services.adapters.base_adapter import OmnichannelItem
from src.app.services.clustering_service import ClusteringService
from src.app.services.feed_registry_service import FeedRegistryService
from src.app.services.omnichannel_intelligence_service import OmnichannelIntelligenceService


def make_item(title, url, source, platform="blog"):
    return OmnichannelItem(
        id=f"{platform}_{source}",
        platform=platform,
        source_name=source,
        title=title,
        url=url,
        published_at=datetime.now(timezone.utc),
        summary_hint=title,
        content_text=title
    )


class TestIntelligencePipeline(unittest.TestCase):
    def test_tracking_parameters_are_removed_without_dropping_story_ids(self):
        self.assertEqual(
            ClusteringService._normalize_url("https://news.example/story?utm_source=feed&ref=home"),
            ClusteringService._normalize_url("https://news.example/story")
        )
        self.assertNotEqual(
            ClusteringService._normalize_url("https://news.example/story?id=1"),
            ClusteringService._normalize_url("https://news.example/story?id=2")
        )

    def test_same_story_from_multiple_sources_is_retained_in_one_cluster(self):
        items = [
            make_item(
                "OpenAI launches GPT-5",
                "https://news.example/story?utm_source=feed",
                "Tech News",
                "blog"
            ),
            make_item(
                "GPT-5 model launch",
                "https://news.example/story",
                "Hacker News",
                "hackernews"
            )
        ]

        clusters = ClusteringService.cluster_items(items)

        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].items), 2)
        self.assertEqual(clusters[0].platforms, {"blog", "hackernews"})
        self.assertEqual(clusters[0].sources, {"Tech News", "Hacker News"})

    def test_duplicate_item_from_same_source_is_only_kept_once(self):
        item = make_item(
            "OpenAI launches GPT-5",
            "https://news.example/story?utm_source=feed",
            "Tech News"
        )

        clusters = ClusteringService.cluster_items([item, item])

        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].items), 1)

    def test_distinct_cluster_reports_with_same_title_get_distinct_files(self):
        clusters = ClusteringService.cluster_items([
            make_item("OpenAI releases a model", "https://news.example/model", "Source A"),
            make_item("Google opens a new office", "https://news.example/office", "Source B")
        ])
        analysis = {
            "topic_title": "Daily technology update",
            "executive_summary": "A short factual summary.",
            "key_entities": []
        }

        with TemporaryDirectory() as temp_dir, patch.object(settings, "SUMMARIES_PATH", Path(temp_dir)):
            report_paths = [
                OmnichannelIntelligenceService.save_omnichannel_markdown(cluster, analysis)
                for cluster in clusters
            ]
            OmnichannelIntelligenceService.save_omnichannel_markdown(clusters[0], analysis)

            self.assertEqual(len(set(report_paths)), 2)
            self.assertTrue(all(path.exists() for path in report_paths))
            self.assertEqual(len(list(report_paths[0].parent.glob("*.md"))), 2)

    def test_same_company_does_not_merge_unrelated_developments(self):
        items = [
            make_item("OpenAI releases a new model", "https://news.example/model", "Source A"),
            make_item("OpenAI opens a London office", "https://news.example/office", "Source B")
        ]

        clusters = ClusteringService.cluster_items(items)

        self.assertEqual(len(clusters), 2)

    def test_source_only_synthesis_does_not_invent_impact_or_reaction(self):
        cluster = ClusteringService.cluster_items([
            make_item(
                "A new open-source compiler is released",
                "https://news.example/compiler",
                "Project Blog"
            )
        ])[0]

        analysis = OmnichannelIntelligenceService._build_source_only_synthesis(cluster)

        self.assertEqual(analysis["analysis_status"], "source_only")
        self.assertIn("not support an impact conclusion", analysis["industry_impact"][0])
        self.assertIn("No discussion comments", analysis["community_reaction"][0])
        self.assertIn("Project Blog", analysis["feature_release_details"][0])

    def test_feed_registry_has_unique_named_sources(self):
        feeds = FeedRegistryService.load_feeds(settings.FEEDS_CONFIG_PATH)
        names = [feed["name"] for feed in feeds]

        self.assertGreaterEqual(len(feeds), 35)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(any("Nigeria" in name for name in names))
        self.assertTrue(any("Apple" in name for name in names))


if __name__ == "__main__":
    unittest.main()
