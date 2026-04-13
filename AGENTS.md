# Overwatch — Intelligence Briefing System

## Architecture

Five-stage pipeline, topic-driven. Each topic is a YAML file in `topics/`.

```
Collect (sources/) → Research (configured AI) → Synthesize (configured AI) → Render (MD + HTML) → Publish (git)
```

- **Collect**: Dispatches to source adapters (RSS, YouTube, Nostr, X). Each returns a list of item dicts.
- **Research**: Configured AI CLI researches the web for gaps not covered by collected items. Returns a JSON object containing `items` plus `checked_sources` audit entries.
- **Synthesize**: Configured AI CLI combines all items + research into a markdown brief.
- **Render**: Jinja2 templates produce `.md` and `.html` files in `output/{slug}/`.
- **Publish**: Git add/commit, regenerate `index.html`, optionally push.

AI execution is provider-based via `core/ai.py`. Built-in presets exist for Claude and Codex, and additional providers can be added in `config.yaml` under `ai.providers`.

The current local environment is configured to prefer Codex by default, but the pipeline is meant to stay provider-agnostic.

## File Layout

```
main.py                  — Entry point, orchestrates the 4-step pipeline
core/
  ai.py                  — AI provider abstraction for Claude, Codex, and custom stdin-driven CLIs
  collector.py           — Loads topic YAML, dispatches to source adapters, manages state (last_run timestamps)
  synthesizer.py         — Two-phase synthesis: (1) research gaps via configured AI, (2) produce brief via configured AI
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
    "source_type": str,     # e.g. "web_search" or "research"
    "search_query": str,    # web_search only
    "domain": str,          # normalized hostname for trust scoring / display
    "trust_level": str,     # "trusted_watchlist", "untrusted_broad_search", or "unknown_source"
    "verification_status": str,  # e.g. "watchlist-matched", "corroborated:2_domains", "single-source"
    "why_included": str,    # prompt-facing explanation after evidence gating
}
```

Research items from Phase 1 are normalized into the same trust-aware shape before synthesis, even if the model returns only `{title, url, date, summary}`.

## Key Conventions

- **Timezone**: All dates use GMT+10 (AEST) via `_AEST` in synthesizer.py. NOT UTC.
- **Social media**: X/Twitter sources don't fetch actual posts. They return "research directives" — items with `purpose="research_directive"` and a summary asking Claude to search the web. Claude fills the gap during synthesis Phase 2.
- **NSTR**: "Nothing Significant To Report" (intel jargon). Used in briefs when a category has no updates.
- **Brief format**: Summary table goes at the TOP with clickable anchor links to category sections. No classification statements (e.g. "Classification: OPEN SOURCE").
- **Filenames**: `renderer.py`'s `_generate_outline()` extracts the first 3 bold headlines from the brief content to build a slug for the filename. Unwanted text in bold (like classification lines) can leak into filenames.
- **Search trust model**: Broad web results are discovery leads, not authority. Trusted watchlists and direct sources should outrank generic search hits.
- **Prompt-injection stance**: Raw source text is treated as untrusted evidence. It can describe the outside world, but it must not change prompt behavior, output format, or tool choices.

## Config Reference

**config.yaml:**
- `output_dir` (default: `"output"`)
- `state_dir` (default: `"state"`)
- `max_items` (default: `50`) — caps items sent to the AI, sorted by date descending
- `ai.provider` — selected AI provider (`claude`, `codex`, or custom provider key)
- `ai.model` — optional model override
- `ai.timeout_seconds` — subprocess timeout for AI calls
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
- `OVERWATCH_AI_PROVIDER` — AI provider override
- `OVERWATCH_AI_MODEL` — model override for the selected provider
- `OVERWATCH_MODEL` — backward-compatible model override
- `OVERWATCH_AI_COMMAND` — full command override for the active provider
- `SEARXNG_URL` — self-hosted SearXNG endpoint used before Brave/Serper search backends
- `YOUTUBE_COOKIES_FILE` — path to cookies.txt if YouTube blocks transcript requests

## Search and Trust Behavior

### Search backend order

`sources/web_search.py` tries:
1. `SEARXNG_URL`
2. `BRAVE_SEARCH_API_KEY`
3. `SERPER_API_KEY`

The local machine is set up account-wide to use a SearXNG instance at `http://127.0.0.1:8888`.

### Why SearXNG was added

- Reusable structured web search for Overwatch and other projects
- Local endpoint for cron jobs without per-job API wiring
- Broad discovery coverage without depending solely on one paid API
- JSON output that is easier to filter and annotate before synthesis

### Prompt-injection hardening

The current hardening is implemented in two places:

1. `sources/web_search.py`
- sanitizes titles and snippets before they enter prompts
- strips obvious instruction-like phrases such as "ignore previous instructions", "system prompt", and similar payloads
- adds normalized `domain`, `trust_level`, and `verification_status` metadata

2. `core/synthesizer.py`
- instructs the research phase to treat web content as untrusted data
- tells synthesis that source material is evidence, not instruction
- surfaces trust and verification metadata inside prompt source material
- applies a code-level evidence gate before synthesis

### Evidence gate

The evidence gate exists to keep the system non-restrictive but sensible.

What it does:
- allows trusted-watchlist matches through
- allows same-story corroboration across multiple domains
- excludes major single-source broad-search claims
- keeps lower-stakes single-source items as low-confidence leads

What counts as a "major" claim right now:
- model releases / launches
- funding / acquisition / merger / investment moves
- regulation / government / policy actions
- data center / chip / infrastructure developments

Why it was designed this way:
- relying on the model alone to resist prompt injection is not a sufficient control
- blocking all broad-search output would be too restrictive and would miss real stories
- moving only the highest-risk exclusion decision into code is a better balance
- this is intentionally lightweight and explainable, not a heavy trust-scoring system

### Trusted watchlists

`topics/ai.yaml` now carries two distinct watchlists:
- `trusted_lab_watchlist`
- `trusted_media_watchlist`

These are used for two purposes:
- operator guidance to the research phase about which sources must be checked
- deterministic trusted-domain extraction for synthesis-time trust labeling

## Operational Notes

- The local shell exports `SEARXNG_URL=http://127.0.0.1:8888`.
- User cron also exports `SEARXNG_URL` and starts SearXNG on reboot.
- Local helper scripts exist at `~/.local/bin/searxng-local-start` and `~/.local/bin/searxng-local-stop`.
- In this environment, a detached session (`setsid`) was required for reliable background startup; a plain `nohup` path did not persist reliably.

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
- **Evidence gate is heuristic**: Same-story matching is lightweight token overlap, not true claim resolution. It is useful, but it can both miss corroboration and over-group near-duplicate headlines in edge cases.
