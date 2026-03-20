import json
import os
from datetime import datetime, timezone

import yaml

from sources import rss, api, scraper, youtube, social

ADAPTERS = {
    "rss": rss,
    "api": api,
    "scraper": scraper,
    "youtube_channel": youtube,
    "youtube_search": youtube,
    "social": social,
}


def load_topic(topic_slug, topics_dir="topics"):
    """Load a topic configuration by slug."""
    path = os.path.join(topics_dir, f"{topic_slug}.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def get_last_run(topic_slug, state_dir="state"):
    """Get the timestamp of the last successful run for a topic."""
    path = os.path.join(state_dir, f"{topic_slug}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    ts = data.get("last_run")
    if ts:
        return datetime.fromisoformat(ts)
    return None


def save_last_run(topic_slug, state_dir="state"):
    """Save the current timestamp as last run for a topic."""
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"{topic_slug}.json")
    with open(path, "w") as f:
        json.dump({"last_run": datetime.now(timezone.utc).isoformat()}, f)


def collect(topic_config, since=None):
    """Collect items from all sources defined in a topic config."""
    all_items = []

    for source in topic_config.get("sources", []):
        source_type = source.get("type", "rss")
        adapter = ADAPTERS.get(source_type)
        if not adapter:
            print(f"  Warning: unknown source type '{source_type}', skipping")
            continue

        try:
            items = adapter.fetch(source, since=since)
            print(f"  [{source_type}] {source.get('name', '?')}: {len(items)} items")
            all_items.extend(items)
        except NotImplementedError as e:
            print(f"  [{source_type}] {source.get('name', '?')}: {e}")
        except Exception as e:
            print(f"  [{source_type}] {source.get('name', '?')}: error - {e}")

    return all_items
