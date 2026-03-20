"""Social media source adapter — X/Twitter, Nostr, YouTube channels."""

import json
from datetime import datetime, timezone, timedelta

import requests
import websocket


def fetch(source_config, since=None):
    """Fetch recent posts from a social media account."""
    platform = source_config.get("platform", "")

    if platform == "nostr":
        return fetch_nostr(source_config, since)
    elif platform == "x":
        return fetch_x(source_config, since)
    else:
        print(f"    Unknown social platform: {platform}")
        return []


def fetch_nostr(source_config, since=None):
    """Fetch recent notes from a Nostr user via public APIs."""
    handle = source_config.get("handle", "")
    name = source_config.get("name", handle)

    pubkey = source_config.get("pubkey") or _resolve_nostr_pubkey(source_config)
    if not pubkey:
        print(f"    Could not resolve Nostr pubkey for {handle}")
        return []

    since_ts = int(since.timestamp()) if since else int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())

    # Query Nostr relays directly via WebSocket (most reliable)
    relays = [
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.primal.net",
    ]

    for relay_url in relays:
        try:
            notes = _fetch_from_relay(relay_url, pubkey, since_ts)
            if notes:
                items = []
                for note in notes:
                    items.append({
                        "title": f"{name} (Nostr)",
                        "url": f"https://primal.net/e/{note.get('id', '')}",
                        "summary": note.get("content", "")[:1000],
                        "date": datetime.fromtimestamp(
                            note.get("created_at", 0), tz=timezone.utc
                        ).isoformat(),
                        "source_name": name,
                    })
                return items
        except Exception as e:
            print(f"    Relay {relay_url} error: {e}")
            continue

    # Fallback: return a research directive for Claude
    print(f"    All Nostr relays failed for {handle} — delegating to research phase")
    return [{
        "title": f"{name} (Nostr) — recent activity",
        "url": source_config.get("urls", [f"https://primal.net/{handle}"])[0],
        "summary": (
            f"RESEARCH DIRECTIVE: Search the web for recent Nostr posts and activity "
            f"from {name} (handle: {handle}) in the last 24 hours. "
            f"Check primal.net/{handle} or nostr.band for their recent notes."
        ),
        "date": datetime.now(timezone.utc).isoformat(),
        "source_name": name,
        "purpose": "research_directive",
    }]


def _fetch_from_relay(relay_url, pubkey, since_ts):
    """Fetch kind-1 notes from a Nostr relay using NIP-01 WebSocket protocol."""
    ws = websocket.create_connection(relay_url, timeout=10)
    sub_id = "overwatch"

    req = json.dumps([
        "REQ", sub_id,
        {
            "authors": [pubkey],
            "kinds": [1],
            "since": since_ts,
            "limit": 20,
        }
    ])
    ws.send(req)

    notes = []
    while True:
        raw = ws.recv()
        msg = json.loads(raw)
        if msg[0] == "EOSE":
            break
        if msg[0] == "EVENT" and msg[1] == sub_id:
            notes.append(msg[2])

    ws.send(json.dumps(["CLOSE", sub_id]))
    ws.close()
    return notes


def _resolve_nostr_pubkey(source_config):
    """Try to resolve a Nostr pubkey from handle via multiple methods."""
    handle = source_config.get("handle", "")

    # Method 1: NIP-05 lookup (handle@domain)
    nip05 = source_config.get("nip05")
    if nip05 and "@" in nip05:
        user, domain = nip05.split("@", 1)
        try:
            resp = requests.get(
                f"https://{domain}/.well-known/nostr.json?name={user}",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                pk = data.get("names", {}).get(user)
                if pk:
                    return pk
        except Exception:
            pass

    # Method 2: nostr.band profile search
    try:
        resp = requests.get(
            f"https://api.nostr.band/v0/search?q={handle}&type=profiles",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            profiles = data.get("profiles", [])
            for p in profiles:
                event = p.get("event", {})
                # Match by checking if handle appears in name/about
                content = json.loads(event.get("content", "{}"))
                if handle.lower() in content.get("name", "").lower():
                    return event.get("pubkey")
    except Exception:
        pass

    # Method 3: Try well-known NIP-05 domains
    for domain in ["nostr.com", f"{handle}.com"]:
        try:
            resp = requests.get(
                f"https://{domain}/.well-known/nostr.json?name={handle}",
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                pk = data.get("names", {}).get(handle)
                if pk:
                    return pk
        except Exception:
            continue

    return None


def fetch_x(source_config, since=None):
    """Fetch recent posts from X/Twitter.

    Since all nitter instances are behind Cloudflare or dead,
    we return a research directive so Claude's research phase
    will search for these posts during synthesis.
    """
    handle = source_config.get("handle", "")
    name = source_config.get("name", handle)

    # Return a research directive — Claude will search for their posts
    return [{
        "title": f"{name} (@{handle}) — recent X/Twitter activity",
        "url": f"https://x.com/{handle}",
        "summary": (
            f"RESEARCH DIRECTIVE: Search the web for recent posts and activity "
            f"from @{handle} ({name}) on X/Twitter in the last 24 hours. "
            f"Look for noteworthy tweets, threads, announcements, or discussions."
        ),
        "date": datetime.now(timezone.utc).isoformat(),
        "source_name": name,
        "purpose": "research_directive",
    }]
