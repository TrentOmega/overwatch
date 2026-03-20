# Overwatch

Intelligence briefing system. Collects from multiple source types, uses Claude to research gaps and synthesize, outputs markdown and HTML briefs.

## How it works

```
Collect (RSS, YouTube, Nostr, X/Twitter) → Research (Claude web search) → Synthesize (Claude) → Render (MD + HTML) → Publish (git commit)
```

Adding a new topic is just a YAML file in `topics/`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires [Claude Code](https://claude.ai/code) installed and authenticated — no API key needed.

## Usage

```bash
# Run a single topic
python main.py --topic ai

# Run all topics
python main.py --topic all

# Dry run (no publish)
python main.py --topic ai --dry-run

# List available topics
python main.py --list
```

## Adding a topic

Copy `topics/_template.yaml` and configure sources, categories, and synthesis rules:

```bash
cp topics/_template.yaml topics/bitcoin.yaml
# Edit topics/bitcoin.yaml
python main.py --topic bitcoin
```

## Source types

| Type | Description |
|---|---|
| `rss` | RSS/Atom feeds |
| `youtube_channel` | Latest videos from a channel (with transcript extraction) |
| `youtube_search` | Search YouTube by query, filter by views/recency |
| `social` (x) | X/Twitter monitoring (via Claude research fallback) |
| `social` (nostr) | Nostr notes via direct relay WebSocket queries |

## Cron

```cron
0 7 * * *   cd /path/to/overwatch && .venv/bin/python main.py --topic ai
```

## Output

Briefs are rendered to `output/<topic>/<date>_<slug>.md` and `.html`.

HTML copies are also published to the repo root for GitHub Pages, with an `index.html` listing all briefs.

## YouTube transcripts

If YouTube blocks transcript requests (IP-based), export cookies from your browser:

```bash
yt-dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download "https://youtube.com"
```

Then set `YOUTUBE_COOKIES_FILE=./cookies.txt` in `.env`.
