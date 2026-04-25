import importlib.util
import os
from urllib.parse import urlparse

import requests

from sources.web_search import _is_local_searxng, _try_start_local_searxng


def check_runtime_health(topic_config):
    """Return blocking runtime health issues for configured sources."""
    issues = []
    source_types = {source.get("type") for source in topic_config.get("sources", [])}

    if "web_search" in source_types:
        issues.extend(_check_search_health())

    if "youtube_search" in source_types:
        issues.extend(_check_yt_dlp_health())

    return issues


def _check_search_health():
    """Validate that at least one web-search backend is usable."""
    issues = []

    searxng_url = os.getenv("SEARXNG_URL")
    if searxng_url:
        if _is_local_searxng(searxng_url):
            _try_start_local_searxng()

        if _url_reachable(searxng_url):
            return issues

        if os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("SERPER_API_KEY"):
            issues.append({
                "severity": "warning",
                "message": f"SearXNG endpoint unavailable at {searxng_url}; falling back to other configured search backends.",
            })
            return issues

        issues.append({
            "severity": "critical",
            "message": f"SearXNG endpoint unavailable at {searxng_url} and no Brave/Serper fallback is configured.",
        })
        return issues

    if os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("SERPER_API_KEY"):
        return issues

    issues.append({
        "severity": "critical",
        "message": "web_search source configured but no search backend is available. Set SEARXNG_URL, BRAVE_SEARCH_API_KEY, or SERPER_API_KEY.",
    })
    return issues


def _check_yt_dlp_health():
    """Validate that yt-dlp is importable in the active Python environment."""
    if importlib.util.find_spec("yt_dlp") is not None:
        return []

    return [{
        "severity": "critical",
        "message": "youtube_search source configured but yt-dlp is not importable in the active Python environment.",
    }]


def _url_reachable(base_url):
    """Return True if the base URL responds successfully."""
    try:
        parsed = urlparse(base_url)
        health_url = f"{parsed.scheme}://{parsed.netloc}/"
        response = requests.get(health_url, timeout=5)
        response.raise_for_status()
        return True
    except Exception:
        return False
