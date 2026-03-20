import feedparser
from datetime import datetime, timezone


def fetch(source_config, since=None):
    """Fetch items from an RSS feed, optionally filtering by date."""
    feed = feedparser.parse(source_config["url"])
    items = []

    for entry in feed.entries:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

        if since and published and published <= since:
            continue

        items.append({
            "title": entry.get("title", "Untitled"),
            "url": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "date": published.isoformat() if published else None,
            "source_name": source_config["name"],
        })

    return items
