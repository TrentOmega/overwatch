"""YouTube source adapters — channel videos and search-based discovery."""

import os
import re
import json
from datetime import datetime, timezone, timedelta

import requests
from youtube_transcript_api import YouTubeTranscriptApi

# Optional cookies file for bypassing YouTube IP blocks
COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE", os.path.join(os.path.dirname(__file__), "..", "cookies.txt"))



def fetch(source_config, since=None):
    """Dispatch to the right YouTube fetcher based on source type."""
    source_type = source_config.get("type")
    if source_type == "youtube_channel":
        return fetch_channel(source_config, since)
    elif source_type == "youtube_search":
        return fetch_search(source_config, since)
    return []


def fetch_channel(source_config, since=None):
    """Fetch recent videos from a YouTube channel and optionally extract transcripts."""
    channel_url = source_config["channel_url"]
    max_videos = source_config.get("max_videos", 3)
    extract = source_config.get("extract")

    # Get channel RSS feed (YouTube provides one for every channel)
    channel_id = _resolve_channel_id(channel_url)
    if not channel_id:
        print(f"    Could not resolve channel ID for {channel_url}")
        return []

    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    import feedparser
    feed = feedparser.parse(feed_url)

    items = []
    for entry in feed.entries[:max_videos]:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        if since and published and published <= since:
            continue

        video_id = _extract_video_id(entry.get("link", ""))
        summary = entry.get("summary", "")

        if extract == "transcript" and video_id:
            transcript = get_transcript(video_id)
            if transcript:
                summary = transcript

        items.append({
            "title": entry.get("title", "Untitled"),
            "url": entry.get("link", ""),
            "summary": summary,
            "date": published.isoformat() if published else None,
            "source_name": source_config["name"],
            "video_id": video_id,
            "purpose": source_config.get("purpose", "general"),
        })

    return items


def fetch_search(source_config, since=None):
    """Search YouTube for videos matching a query, filter by views, extract transcripts."""
    query = source_config["query"]
    period_hours = source_config.get("period_hours", 24)
    min_views = source_config.get("min_views", 10000)
    max_results = source_config.get("max_results", 10)
    extract = source_config.get("extract")

    # Use yt-dlp for search (no API key needed)
    try:
        import subprocess
        cmd = [
            "yt-dlp",
            f"ytsearch{max_results * 2}:{query}",  # fetch extra to filter
            "--dump-json",
            "--flat-playlist",
            "--no-download",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"    yt-dlp search failed: {result.stderr[:200]}")
            return []

        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=period_hours)

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                video = json.loads(line)
            except json.JSONDecodeError:
                continue

            view_count = video.get("view_count") or 0
            if view_count < min_views:
                continue

            upload_date = video.get("upload_date")  # YYYYMMDD
            if upload_date:
                try:
                    pub_date = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
                    if pub_date < cutoff:
                        continue
                except ValueError:
                    pass

            video_id = video.get("id", "")
            summary = video.get("description", "")[:500]

            if extract == "transcript" and video_id:
                transcript = get_transcript(video_id)
                if transcript:
                    summary = transcript

            items.append({
                "title": video.get("title", "Untitled"),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "summary": summary,
                "date": upload_date,
                "source_name": source_config["name"],
                "video_id": video_id,
                "view_count": view_count,
                "purpose": source_config.get("purpose", "general"),
            })

            if len(items) >= max_results:
                break

        return items

    except FileNotFoundError:
        print("    yt-dlp not installed — install with: pip install yt-dlp")
        return []
    except Exception as e:
        print(f"    YouTube search error: {e}")
        return []


def get_transcript(video_id):
    """Extract transcript text from a YouTube video.

    Tries in order:
    1. youtube-transcript-api (with cookies if available)
    2. yt-dlp subtitle extraction (with cookies if available)
    """
    cookies_path = COOKIES_FILE if os.path.isfile(COOKIES_FILE) else None

    # Method 1: youtube-transcript-api
    try:
        ytt_api = YouTubeTranscriptApi()
        kwargs = {}
        if cookies_path:
            kwargs["cookies"] = cookies_path
        transcript = ytt_api.fetch(video_id, **kwargs)
        text = " ".join(snippet.text for snippet in transcript.snippets)
        if len(text) > 15000:
            text = text[:15000] + "\n[...transcript truncated]"
        return text
    except Exception:
        pass

    # Method 2: yt-dlp subtitle extraction
    try:
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            url = f"https://www.youtube.com/watch?v={video_id}"
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-auto-sub",
                "--write-sub",
                "--sub-lang", "en",
                "--sub-format", "json3",
                "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
                url,
            ]
            if cookies_path:
                cmd.extend(["--cookies", cookies_path])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Look for json3 subtitle file first, then srt/vtt
            sub_file = None
            for f in os.listdir(tmpdir):
                if f.endswith(".json3"):
                    sub_file = os.path.join(tmpdir, f)
                    break
                if f.endswith((".srt", ".vtt")) and not sub_file:
                    sub_file = os.path.join(tmpdir, f)

            if sub_file:
                with open(sub_file) as f:
                    raw = f.read()
                if sub_file.endswith(".json3"):
                    text = _parse_json3(raw)
                else:
                    text = _parse_srt(raw)
                if len(text) > 15000:
                    text = text[:15000] + "\n[...transcript truncated]"
                return text
    except Exception as e:
        print(f"    yt-dlp subtitle extraction failed for {video_id}: {e}")

    print(f"    Transcript unavailable for {video_id}")
    return None


def _parse_json3(json_text):
    """Extract plain text from YouTube json3 subtitle format."""
    data = json.loads(json_text)
    segments = []
    for event in data.get("events", []):
        text = "".join(seg.get("utf8", "") for seg in event.get("segs", []))
        text = text.strip()
        if text and text != "\n":
            segments.append(text)
    return " ".join(segments)


def _parse_srt(srt_text):
    """Extract plain text from SRT subtitle content, removing duplicates."""
    lines = []
    seen = set()
    for line in srt_text.split("\n"):
        line = line.strip()
        if not line or re.match(r"^\d+$", line) or re.match(r"^\d{2}:\d{2}", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return " ".join(lines)


def _resolve_channel_id(channel_url):
    """Resolve a YouTube channel URL to a channel ID."""
    # Direct channel ID URL
    match = re.search(r"/channel/(UC[\w-]+)", channel_url)
    if match:
        return match.group(1)

    # Handle /@username or /c/name URLs by fetching the page
    try:
        resp = requests.get(channel_url, timeout=10)
        match = re.search(r'"channelId":"(UC[\w-]+)"', resp.text)
        if match:
            return match.group(1)
        match = re.search(r'channel_id=(UC[\w-]+)', resp.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"    Error resolving channel: {e}")

    return None


def _extract_video_id(url):
    """Extract video ID from a YouTube URL."""
    match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    return match.group(1) if match else None
