import json
import os
import subprocess
from datetime import datetime, timezone


def synthesize(items, topic_config, model=None):
    """Two-phase synthesis: research gaps, then produce the brief."""
    model = model or os.getenv("OVERWATCH_MODEL")

    # Phase 1: Claude researches the web to fill gaps
    print("  Phase 1: Web research for gaps...")
    research = _research_phase(items or [], topic_config, model)
    print(f"  Found {len(research)} additional items via research")

    # Phase 2: Claude synthesizes everything into the final brief
    print("  Phase 2: Synthesizing brief...")
    return _synthesis_phase(items or [], research, topic_config, model)


def _research_phase(items, topic_config, model):
    """Have Claude search the web for news the structured sources may have missed."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    synthesis_config = topic_config.get("synthesis", {})

    categories = synthesis_config.get("categories", [])
    cat_list = "\n".join(f"- {c['name']}: {c.get('scope', '')}" for c in categories)

    # Summarise what we already have so Claude knows the gaps
    existing_summary = "No items collected from structured sources." if not items else (
        f"{len(items)} items already collected:\n" +
        "\n".join(f"- {item['title']}" for item in items[:30])
    )

    prompt = f"""You are a research assistant. Today is {today}.

Topic: {topic_config['name']}

The following items have already been collected from RSS feeds, podcasts, and social media:

{existing_summary}

Your job: search the web for any significant developments in the last ~24 hours
that are NOT already covered above. Focus on these categories:

{cat_list}

Instructions:
- Use web search to find recent news, announcements, and developments
- Focus on primary sources (official blogs, Reuters, major outlets)
- Only include items from the last ~24 hours
- Skip anything already covered in the existing items above
- For each item found, provide: title, URL, date, and a 1-2 sentence summary

Output your findings as a JSON array of objects with keys: title, url, date, summary
If you find nothing new, output an empty array: []
Output ONLY the JSON array, no other text."""

    result = _run_claude(prompt, model)

    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        # If Claude returned prose instead of JSON, try to extract the array
        start = result.find("[")
        end = result.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(result[start:end])
            except json.JSONDecodeError:
                pass
        return []


def _synthesis_phase(items, research_items, topic_config, model):
    """Combine collected items + research into the final brief."""
    if not items and not research_items:
        return _empty_brief(topic_config)

    synthesis_config = topic_config.get("synthesis", {})
    system_prompt = synthesis_config.get("system_prompt", "You are an intelligence analyst.")

    user_prompt = _build_prompt(items, research_items, topic_config, synthesis_config)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    return _run_claude(full_prompt, model)


def _run_claude(prompt, model=None):
    """Run a prompt through the Claude CLI via stdin to avoid arg length limits."""
    import tempfile

    cmd = ["claude", "-p", "-"]
    if model:
        cmd.extend(["--model", model])

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=600, env=env, cwd="/tmp")

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr[:500]}")

    return result.stdout.strip()


def _build_prompt(items, research_items, topic_config, synthesis_config):
    """Build the full synthesis prompt with all sources and format rules."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Separate collected items by type
    general_items = []
    transcript_items = []
    social_items = []

    for item in items:
        purpose = item.get("purpose", "")
        if purpose in ("podcast_summary", "workflow_extraction"):
            transcript_items.append(item)
        elif "(@" in item.get("title", "") or "(Nostr)" in item.get("title", ""):
            social_items.append(item)
        else:
            general_items.append(item)

    parts = [
        f"# Intelligence Brief — {today}",
        f"Topic: {topic_config['name']}",
        "",
    ]

    # Section 1: Pre-collected items
    if general_items:
        parts.append("## Source Material: News & Updates (from RSS feeds)")
        parts.append(_format_items(general_items))
        parts.append("")

    if transcript_items:
        parts.append("## Source Material: Podcast Transcripts & YouTube Content")
        parts.append(_format_items(transcript_items, include_full_summary=True))
        parts.append("")

    if social_items:
        parts.append("## Source Material: Social Media Posts")
        parts.append(_format_items(social_items))
        parts.append("")

    # Section 2: Research findings from Claude's web search
    if research_items:
        parts.append("## Source Material: Web Research (found via search)")
        for i, item in enumerate(research_items, 1):
            lines = [f"[R{i}] {item.get('title', 'Untitled')}"]
            if item.get("url"):
                lines.append(f"    URL: {item['url']}")
            if item.get("date"):
                lines.append(f"    Date: {item['date']}")
            if item.get("summary"):
                lines.append(f"    Summary: {item['summary']}")
            parts.append("\n".join(lines))
        parts.append("")

    if not general_items and not transcript_items and not social_items and not research_items:
        parts.append("No source material was collected or found. Mark all categories NSTR.")
        parts.append("")

    # Categories
    categories = synthesis_config.get("categories", [])
    if categories:
        parts.append("## Required Output Categories (in this exact order)")
        for i, cat in enumerate(categories, 1):
            parts.append(f"{i}) {cat['name']}")
            if cat.get("scope"):
                parts.append(f"   Scope: {cat['scope']}")
        parts.append("")

    # Format rules
    format_rules = synthesis_config.get("format_rules", "")
    if format_rules:
        parts.append("## Format Rules")
        parts.append(format_rules)
        parts.append("")

    # Focus areas
    focus_areas = synthesis_config.get("focus_areas", [])
    if focus_areas:
        parts.append("## Focus Areas")
        for area in focus_areas:
            parts.append(f"- {area}")
        parts.append("")

    parts.append("""Produce a COMPLETE, STANDALONE intelligence brief now.

CRITICAL INSTRUCTIONS:
- Output the FULL brief with ALL categories populated (or marked NSTR)
- This is NOT an update or diff — produce the entire document from scratch
- Start with a markdown heading: "# AI Daily Brief — YYYY-MM-DD"
- Include ALL 9 categories in order, each with its own ## heading
- End with the summary table
- Use ALL the source material above — do not search the web again
- Do NOT output meta-commentary about what changed — just produce the brief itself""")

    return "\n".join(parts)


def _format_items(items, include_full_summary=False):
    """Format collected items into text for the prompt."""
    parts = []
    for i, item in enumerate(items, 1):
        lines = [f"[{i}] {item['title']}"]
        if item.get("url"):
            lines.append(f"    URL: {item['url']}")
        if item.get("source_name"):
            lines.append(f"    Source: {item['source_name']}")
        if item.get("date"):
            lines.append(f"    Date: {item['date']}")
        if item.get("view_count"):
            lines.append(f"    Views: {item['view_count']:,}")
        if item.get("summary"):
            max_len = 5000 if include_full_summary else 500
            summary = item["summary"][:max_len]
            lines.append(f"    Summary: {summary}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _empty_brief(topic_config):
    """Return a placeholder when no items were collected."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"# {topic_config['name']} Brief — {today}\n\nNo new items collected for this period."
