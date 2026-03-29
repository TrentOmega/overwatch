# Overwatch

Intelligence briefing system. Collects from multiple source types, uses a configurable AI CLI to research gaps and synthesize, outputs markdown and HTML briefs.

## How it works

```
Collect (RSS, YouTube, Nostr, X/Twitter) → Research (configured AI) → Synthesize (configured AI) → Render (MD + HTML) → Publish (git commit)
```

Adding a new topic is just a YAML file in `topics/`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires at least one supported AI CLI installed and authenticated.

Built-in presets:
- `claude` via [Claude Code](https://claude.ai/code)
- `codex` via the local `codex` CLI

You can also define a custom stdin-driven CLI command in `config.yaml` or `OVERWATCH_AI_COMMAND`.

## Usage

```bash
# Run a single topic
python main.py --topic ai

# Run with Claude instead of the default provider
python main.py --topic ai --ai-provider claude

# Run all topics
python main.py --topic all

# Dry run (no publish)
python main.py --topic ai --dry-run

# List available topics
python main.py --list
```

## AI provider configuration

Provider selection priority:
1. CLI flag: `--ai-provider`
2. Env var: `OVERWATCH_AI_PROVIDER`
3. `config.yaml`: `ai.provider`

Model selection priority:
1. CLI flag: `--model`
2. Env var: `OVERWATCH_AI_MODEL`
3. Env var: `OVERWATCH_MODEL` (backward compatibility)
4. `config.yaml`: `ai.model`

Example `config.yaml`:

```yaml
ai:
  provider: codex
  timeout_seconds: 600
  providers:
    claude:
      command: ["claude", "-p", "-"]
      model_flag: "--model"
      strip_env: ["CLAUDECODE"]
      working_dir: /tmp
    codex:
      command: ["codex", "--search", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never", "-"]
      model_flag: "--model"
      output_mode: file
      output_file_flag: "--output-last-message"
      working_dir: /tmp
```

To plug in another provider, add a new entry under `ai.providers` with a command that accepts the prompt on stdin.

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
| `social` (x) | X/Twitter monitoring (via AI research fallback) |
| `social` (nostr) | Nostr notes via direct relay WebSocket queries |

## Cron

```cron
0 7 * * *   cd /path/to/overwatch && .venv/bin/python main.py --topic ai
```

Current local cron entry:

```cron
0 18 * * * cd /home/user/Documents/Projects/overwatch && .venv/bin/python main.py --topic ai >> /tmp/overwatch-cron.log 2>&1
```

With the default config, that job uses Codex. To force Claude for that job instead:

```cron
0 18 * * * cd /home/user/Documents/Projects/overwatch && OVERWATCH_AI_PROVIDER=claude .venv/bin/python main.py --topic ai >> /tmp/overwatch-cron.log 2>&1
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
