import re
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Set
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from src.app.services.adapters.base_adapter import OmnichannelItem
from src.app.utils.logger import logger

@dataclass
class TopicCluster:
    """A unified topic thread grouping overlapping stories from multiple platforms."""
    cluster_id: str
    canonical_title: str
    primary_category: str
    items: List[OmnichannelItem] = field(default_factory=list)
    platforms: Set[str] = field(default_factory=set)
    sources: Set[str] = field(default_factory=set)
    key_entities: List[str] = field(default_factory=list)

    @property
    def is_multi_platform(self) -> bool:
        return len(self.platforms) > 1

    def get_combined_content(self) -> str:
        """Aggregates content across all cluster items for deep LLM analysis."""
        blocks = []
        for item in self.items:
            blocks.append(
                f"### [Source: {item.source_name} | Platform: {item.platform.upper()}]\n"
                f"Title: {item.title}\n"
                f"URL: {item.url}\n"
                f"Author: {item.author or 'Unknown'}\n"
                f"Published: {item.published_at.isoformat() if item.published_at else 'Unknown'}\n"
                f"Signal: {item.summary_hint}\n"
                f"Content & Signal:\n{item.content_text}\n"
            )
        return "\n\n".join(blocks)

class ClusteringService:
    """
    Deduplicates and clusters omnichannel items across YouTube, Reddit, Hacker News,
    GitHub, and Engineering Blogs into single cohesive topic threads.
    """

    # High-signal entities to detect cross-platform stories
    HIGH_SIGNAL_ENTITIES = [
        "gpt-4o", "gpt-4", "gpt-5", "chatgpt", "openai", "sora", "o1", "o3",
        "claude 3.5", "claude 3.7", "claude 3", "claude", "anthropic",
        "gemini 1.5", "gemini 2.0", "gemini flash", "gemini", "deepmind",
        "deepseek-r1", "deepseek-v3", "deepseek",
        "llama 3.3", "llama 3.2", "llama 3", "llama", "meta ai",
        "mistral", "qwen", "huggingface", "vllm", "ollama",
        "blackwell", "b200", "h100", "nvidia", "cuda",
        "react 19", "next.js", "typescript", "rust", "python", "mojo",
        "apple intelligence", "microsoft copilot", "github copilot",
        "agentic", "ai agent", "system design", "layoffs", "funding"
    ]

    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "over", "after",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "new", "how", "what", "why", "when", "show", "hn", "ask", "tell"
    }

    @classmethod
    def _extract_tokens(cls, text: str) -> Set[str]:
        clean = re.sub(r"[^a-zA-Z0-9\s-]", " ", text.lower())
        tokens = set(clean.split())
        return tokens - cls.STOP_WORDS

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""

        parsed = urlsplit(url.strip())
        tracking_params = {
            "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src",
            "source", "utm_campaign", "utm_content", "utm_medium",
            "utm_source", "utm_term"
        }
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in tracking_params and not key.lower().startswith("utm_")
        ]
        path = parsed.path.rstrip("/") or "/"
        return urlunsplit((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urlencode(sorted(query)),
            ""
        ))

    @classmethod
    def _extract_entities(cls, text: str) -> List[str]:
        lower_text = text.lower()
        matched = []
        for ent in cls.HIGH_SIGNAL_ENTITIES:
            if re.search(rf"\b{re.escape(ent)}\b", lower_text):
                matched.append(ent)
        return matched

    @classmethod
    def _compute_similarity(cls, tokens_a: Set[str], tokens_b: Set[str], entities_a: List[str], entities_b: List[str]) -> float:
        """Calculates token Jaccard similarity boosted by shared high-signal entities."""
        if not tokens_a or not tokens_b:
            return 0.0

        shared_entities = set(entities_a).intersection(set(entities_b))

        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)
        jaccard = len(intersection) / len(union) if union else 0.0

        # A shared company or product alone is not enough to merge two stories.
        entity_boost = 0.2 if shared_entities and len(intersection) >= 2 else 0.0
        return jaccard + entity_boost

    @staticmethod
    def _make_cluster_id(item: OmnichannelItem, normalized_url: str) -> str:
        identity = normalized_url or "|".join((
            item.platform.casefold(),
            item.source_name.casefold(),
            " ".join(item.title.casefold().split())
        ))
        return "cluster_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def cluster_items(cls, items: List[OmnichannelItem]) -> List[TopicCluster]:
        """
        Deduplicates items and groups related items into TopicCluster threads.
        """
        if not items:
            return []

        # 1. Topic clustering, retaining separate source records for duplicate URLs.
        clusters: List[TopicCluster] = []
        url_clusters: Dict[str, TopicCluster] = {}
        seen_items = set()

        for item in items:
            item_tokens = cls._extract_tokens(item.title)
            item_entities = cls._extract_entities(f"{item.title} {item.summary_hint}")
            normalized_url = cls._normalize_url(item.url)
            source_identity = normalized_url or item.id or " ".join(item.title.casefold().split())
            item_identity = (
                item.platform.casefold(),
                item.source_name.casefold(),
                source_identity
            )
            if item_identity in seen_items:
                continue
            seen_items.add(item_identity)

            best_match = url_clusters.get(normalized_url) if normalized_url else None
            best_score = 0.0

            if best_match is None:
                for cluster in clusters:
                    for existing_item in cluster.items:
                        cluster_tokens = cls._extract_tokens(existing_item.title)
                        cluster_entities = cls._extract_entities(
                            f"{existing_item.title} {existing_item.summary_hint}"
                        )

                        score = cls._compute_similarity(
                            item_tokens, cluster_tokens, item_entities, cluster_entities
                        )
                        if score > 0.42 and score > best_score:
                            best_score = score
                            best_match = cluster

            if best_match:
                best_match.items.append(item)
                best_match.platforms.add(item.platform)
                best_match.sources.add(item.source_name)
                if normalized_url:
                    url_clusters[normalized_url] = best_match
                # Expand key entities
                for ent in item_entities:
                    if ent not in best_match.key_entities:
                        best_match.key_entities.append(ent)
                # If this item has richer title, update canonical title if appropriate
                if len(item.title) > len(best_match.canonical_title) and item.platform in ("frontier_ai", "blog"):
                    best_match.canonical_title = item.title
            else:
                cid = cls._make_cluster_id(item, normalized_url)
                new_cluster = TopicCluster(
                    cluster_id=cid,
                    canonical_title=item.title,
                    primary_category=item.category,
                    items=[item],
                    platforms={item.platform},
                    sources={item.source_name},
                    key_entities=item_entities
                )
                clusters.append(new_cluster)
                if normalized_url:
                    url_clusters[normalized_url] = new_cluster

        # Prioritize current developments, then corroboration and source count.
        def cluster_priority(cluster: TopicCluster):
            published = [
                item.published_at
                for item in cluster.items
                if item.published_at is not None
            ]
            newest_timestamp = max(
                (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).timestamp()
                for dt in published
            ) if published else datetime.min.replace(tzinfo=timezone.utc).timestamp()
            return newest_timestamp, len(cluster.platforms), len(cluster.items)

        clusters.sort(key=cluster_priority, reverse=True)
        logger.info(f"Clustering complete: {len(items)} items grouped into {len(clusters)} topic clusters.")
        return clusters
