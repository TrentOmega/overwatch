"""Web search source adapter — LLM self-research via search APIs."""

import os
from datetime import datetime, timezone

import requests


def fetch(source_config, since=None):
    """Search the web for recent news on configured queries."""
    queries = source_config.get("queries", [])
    items = []

    for query in queries:
        results = _search(query)
        for r in results:
            items.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "summary": r.get("snippet", ""),
                "date": r.get("date", datetime.now(timezone.utc).isoformat()),
                "source_name": f"Web: {query}",
            })

    return items


def _search(query):
    """Execute a web search. Tries available search backends in order."""
    # Try SearXNG (self-hosted, free)
    searxng_url = os.getenv("SEARXNG_URL")
    if searxng_url:
        return _search_searxng(query, searxng_url)

    # Try Brave Search API (free tier: 2000 queries/mo)
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if brave_key:
        return _search_brave(query, brave_key)

    # Try Serper API (free tier: 2500 queries)
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        return _search_serper(query, serper_key)

    print(f"    No search backend configured. Set one of: SEARXNG_URL, BRAVE_SEARCH_API_KEY, SERPER_API_KEY")
    return []


def _search_searxng(query, base_url):
    """Search using a SearXNG instance."""
    try:
        resp = requests.get(
            f"{base_url}/search",
            params={"q": query, "format": "json", "time_range": "day", "categories": "news"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", ""), "date": r.get("publishedDate", "")}
            for r in data.get("results", [])[:5]
        ]
    except Exception as e:
        print(f"    SearXNG search error: {e}")
        return []


def _search_brave(query, api_key):
    """Search using Brave Search API."""
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "freshness": "pd", "count": 5},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", ""), "date": r.get("age", "")}
            for r in data.get("web", {}).get("results", [])[:5]
        ]
    except Exception as e:
        print(f"    Brave search error: {e}")
        return []


def _search_serper(query, api_key):
    """Search using Serper.dev API."""
    try:
        resp = requests.post(
            "https://google.serper.dev/news",
            json={"q": query, "tbs": "qdr:d", "num": 5},
            headers={"X-API-KEY": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", ""), "date": r.get("date", "")}
            for r in data.get("news", [])[:5]
        ]
    except Exception as e:
        print(f"    Serper search error: {e}")
        return []
