# Overwatch — Intelligence Briefing System

## Architecture

Five-stage pipeline, topic-driven. Each topic is a YAML file in `topics/`.

```
Collect (sources/) → Research (Claude web search) → Synthesize (Claude) → Render (MD + HTML) → Publish (git)
```

- **Collect**: Dispatches to source adapters (RSS, YouTube, Nostr, X). Each returns a list of item dicts.
- **Research**: Claude CLI subprocess searches the web for gaps not covered by collected items. Returns JSON array.
- **Synthesize**: Claude CLI subprocess combines all items + research into a markdown brief.
- **Render**: Jinja2 templates produce `.md` and `.html` files in `output/{slug}/`.
- **Publish**: Git add/commit, regenerate `index.html`, optionally push.

Claude is invoked via `subprocess.run(["claude", "-p", "-"])` with prompt on stdin. The `CLAUDECODE` env var is stripped to avoid conflicts with parent Claude sessions, and `cwd="/tmp"` prevents the subprocess from reading project files.

## File Layout

```
main.py                  — Entry point, orchestrates the 4-step pipeline
core/
  collector.py           — Loads topic YAML, dispatches to source adapters, manages state (last_run timestamps)
  synthesizer.py         — Two-phase synthesis: (1) research gaps via Claude, (2) produce brief via Claude
  renderer.py            — Jinja2 rendering to MD/HTML, filename slug generation from bold headlines
  publisher.py           — Git commit/push, index.html regeneration (scans all output/)
sources/
  rss.py                 — RSS/Atom feed adapter (feedparser)
  youtube.py             — Handles BOTH youtube_channel and youtube_search source types (dispatched by source["type"])
  social.py              — X/Twitter (returns research directives) and Nostr (WebSocket relay queries)
  web_search.py          — Pluggable backends: SearXNG, Brave, Serper
  api.py, scraper.py     — Stubs (NotImplementedError)
topics/
  _template.yaml         — Template for new topics (copy and fill in)
  ai.yaml                — Active AI topic config
templates/
  brief.md.j2            — Markdown output template
  brief.html.j2          — HTML output template (dark theme)
  index.html.j2          — Index page listing all briefs
state/
  {slug}.json            — Last-run timestamp per topic
output/
  {slug}/                — Generated briefs: {date}_{outline}.md and .html
```

## Item Schema

All source adapters return lists of dicts with this shape:

```python
{
    "title": str,           # Required
    "url": str,             # May be empty
    "summary": str,         # May be full transcript (up to 15,000 chars, silently truncated)
    "date": str,            # ISO format from most sources; YYYYMMDD from youtube_search
    "source_name": str,     # Attribution
    # Optional:
    "video_id": str,        # YouTube only
    "view_count": int,      # YouTube search only
    "purpose": str,         # "podcast_summary", "workflow_extraction", "research_directive", or absent
}
```

Research items from Phase 1 have a simpler shape: `{title, url, date, summary}`.

## Key Conventions

- **Timezone**: All dates use GMT+10 (AEST) via `_AEST` in synthesizer.py. NOT UTC.
- **Social media**: X/Twitter sources don't fetch actual posts. They return "research directives" — items with `purpose="research_directive"` and a summary asking Claude to search the web. Claude fills the gap during synthesis Phase 2.
- **NSTR**: "Nothing Significant To Report" (intel jargon). Used in briefs when a category has no updates.
- **Brief format**: Summary table goes at the TOP with clickable anchor links to category sections. No classification statements (e.g. "Classification: OPEN SOURCE").
- **Filenames**: `renderer.py`'s `_generate_outline()` extracts the first 3 bold headlines from the brief content to build a slug for the filename. Unwanted text in bold (like classification lines) can leak into filenames.

## Config Reference

**config.yaml:**
- `output_dir` (default: `"output"`)
- `state_dir` (default: `"state"`)
- `max_items` (default: `50`) — caps items sent to Claude, sorted by date descending
- `model` — optional model override (otherwise uses `OVERWATCH_MODEL` env var)
- `publisher.auto_push` (default: `false`)

**Topic YAML source fields (not all obvious):**
- `extract: transcript` — triggers YouTube transcript extraction
- `purpose` — `"podcast_summary"` or `"workflow_extraction"` changes how item is categorized in synthesis prompt
- `period_hours` (default: 24) — YouTube search recency filter
- `min_views` (default: 10000) — YouTube search minimum view count
- `max_results` (default: 10) — YouTube search result cap
- `nip05` — Nostr NIP-05 identifier for pubkey resolution
- `pubkey` — Nostr hex pubkey

**Environment variables:**
- `OVERWATCH_MODEL` — Claude model to use
- `YOUTUBE_COOKIES_FILE` — path to cookies.txt if YouTube blocks transcript requests

## Common Tasks

- **Add an RSS source**: Add `{type: rss, name: ..., url: ...}` to `sources:` in topic YAML
- **Add a tracked person**: Add a `social` source entry + update the "Notable Voices" category `scope` string
- **Add a new topic**: Copy `topics/_template.yaml`, fill in sources and categories, run `python main.py --topic <slug>`
- **Run**: `python main.py --topic ai [--dry-run]`

## Gotchas

- **No deduplication**: Same article from two RSS feeds appears twice in the synthesis prompt.
- **Date format inconsistency**: YouTube search returns YYYYMMDD strings, everything else is ISO. Sorting treats dates as strings.
- **Transcript truncation**: YouTube transcripts silently cut off at 15,000 chars.
- **Social media detection is fragile**: `synthesizer.py` categorizes items as social by checking for `"(@"` or `"(Nostr)"` in the title string. If title format changes, categorization breaks.
- **Items with no date**: Sorted as string `""`, which sorts before all dates. Won't crash but may be excluded by `max_items` cap.
- **No retry on Claude failure**: If the Claude subprocess fails, the pipeline stops. No fallback.
