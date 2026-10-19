import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.app.config import settings


class FeedRegistryService:
    """Loads either the indexed feed directory or a legacy feeds.json file."""

    @classmethod
    def load_feeds(cls, configured_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        path = configured_path or settings.FEEDS_CONFIG_PATH
        if not path.exists():
            legacy_path = path.with_name("feeds.json")
            if legacy_path.exists():
                path = legacy_path
            else:
                raise FileNotFoundError(f"Feed registry not found at {path}")

        if path.is_file():
            entries = cls._read_json_array(path)
        elif path.is_dir():
            entries = cls._read_feed_directory(path)
        else:
            raise ValueError(f"Feed registry path is not a file or directory: {path}")

        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValueError(f"Feed registry entry {index} must be a JSON object.")
            if not entry.get("name") or not entry.get("url"):
                raise ValueError(f"Feed registry entry {index} must include name and url.")
        return entries

    @classmethod
    def _read_feed_directory(cls, registry_dir: Path) -> List[Dict[str, Any]]:
        index_path = registry_dir / "_index.json"
        expected_total = None
        if index_path.exists():
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(index_data, dict) or not isinstance(index_data.get("files"), list):
                raise ValueError(f"Invalid feed registry index: {index_path}")
            expected_total = index_data.get("total")

            indexed_files = []
            for entry in index_data["files"]:
                if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
                    raise ValueError(f"Invalid feed file entry in {index_path}")
                relative_path = Path(entry["file"])
                if relative_path.is_absolute():
                    raise ValueError(f"Feed paths in {index_path} must be relative.")
                if relative_path.parts and relative_path.parts[0].lower() == registry_dir.name.lower():
                    source_path = registry_dir.parent / relative_path
                else:
                    source_path = registry_dir / relative_path
                resolved_path = source_path.resolve()
                if registry_dir.resolve() not in resolved_path.parents:
                    raise ValueError(f"Feed path escapes the registry directory: {entry['file']}")
                indexed_files.append((resolved_path, entry.get("count")))
        else:
            indexed_files = [
                (feed_file, None)
                for feed_file in sorted(registry_dir.glob("*.json"))
                if feed_file.name != "_index.json"
            ]

        feeds: List[Dict[str, Any]] = []
        for feed_file, expected_count in indexed_files:
            file_feeds = cls._read_json_array(feed_file)
            if expected_count is not None and len(file_feeds) != expected_count:
                raise ValueError(
                    f"Feed count mismatch for {feed_file}: index lists {expected_count}, "
                    f"file contains {len(file_feeds)}."
                )
            feeds.extend(file_feeds)

        if expected_total is not None and len(feeds) != expected_total:
            raise ValueError(
                f"Feed registry total mismatch: index lists {expected_total}, "
                f"loaded {len(feeds)}."
            )
        return feeds

    @staticmethod
    def _read_json_array(path: Path) -> List[Dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Feed registry file must contain a JSON array: {path}")
        return data
