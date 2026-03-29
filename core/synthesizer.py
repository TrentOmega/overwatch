import json
from datetime import datetime, timezone, timedelta

from core.ai import run_prompt

_AEST = timezone(timedelta(hours=10))


def synthesize(items, topic_config, ai_settings):
    """Two-phase synthesis: research gaps, then produce the brief."""
    provider = ai_settings["provider"]

    # Phase 1: use the configured AI to research the web for gaps
    print(f"  Phase 1: Web research for gaps via {provider}...")
    research = _research_phase(items or [], topic_config, ai_settings)
    print(f"  Found {len(research)} additional items via research")

    # Phase 2: synthesize everything into the final brief
    print(f"  Phase 2: Synthesizing brief via {provider}...")
    return _synthesis_phase(items or [], research, topic_config, ai_settings)


def _research_phase(items, topic_config, ai_settings):
    """Have the configured AI search the web for news the structured sources may have missed."""
    today = datetime.now(_AEST).strftime("%Y-%m-%d")
    synthesis_config = topic_config.get("synthesis", {})

    categories = synthesis_config.get("categories", [])
    cat_list = "\n".join(f"- {c['name']}: {c.get('scope', '')}" for c in categories)

    # Summarise what we already have so the AI knows the gaps
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

    result = run_prompt(prompt, ai_settings)

    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        # If the provider returned prose instead of JSON, try to extract the array
        start = result.find("[")
        end = result.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(result[start:end])
            except json.JSONDecodeError:
                pass
        return []


def _synthesis_phase(items, research_items, topic_config, ai_settings):
    """Combine collected items + research into the final brief."""
    if not items and not research_items:
        return _empty_brief(topic_config)

    synthesis_config = topic_config.get("synthesis", {})
    system_prompt = synthesis_config.get("system_prompt", "You are an intelligence analyst.")

    user_prompt = _build_prompt(items, research_items, topic_config, synthesis_config)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    return run_prompt(full_prompt, ai_settings)


def _build_prompt(items, research_items, topic_config, synthesis_config):
    """Build the full synthesis prompt with all sources and format rules."""
    today = datetime.now(_AEST).strftime("%Y-%m-%d")

    # Separate collected items by type
    general_items = []
    transcript_items = []
    social_items = []

    # Categorize items for prompt structure. Social items are detected by title
    # format: social.py includes "(@handle)" for X and "(Nostr)" for Nostr posts.
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

    # Section 2: Research findings from the research phase
    if research_items:
        parts.append("## Source Material: Web Research (found during research phase)")
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
- Do NOT include any classification statement (e.g. "Classification: OPEN SOURCE" or "Period:" lines) — omit these entirely
- Immediately after the heading, include the Summary Table with three columns: #, Category, Signal
- The Summary Table must begin with these exact two lines:
  | # | Category | Signal |
  |---|---|---|
- If a category has no meaningful update, write the signal as EXACTLY `NSTR` and make the section body EXACTLY `NSTR`
- Do NOT paraphrase absence with phrases like "No major release confirmed", "No specific posts provided", or similar
- The table must use this exact format for each row: | 1 | [Category Name](#anchor) | signal text |
- The number column is plain text (NOT a link). The category name column is the clickable anchor link. Example row: | 1 | [New LLMs / Lab Tools](#1-new-llm-versions--major-ai-lab-tools) | Signal text here |
- Do NOT repeat the same underlying story in multiple categories. Choose the single best-fit category and mark the others NSTR if they have no distinct item
- Do NOT populate "Notable Voices" from podcast material. That section is only for actual tracked-person/social-source updates
- Then include ALL 9 categories in order, each with its own NUMBERED ## heading (e.g. "## 1. New LLM Versions / Major AI Lab Tools")
- End with: *Prepared: YYYY-MM-DD* and *Next brief: YYYY-MM-DD*
- Use ALL the source material above — do not search the web again
- Do NOT output meta-commentary about what changed — just produce the brief itself
- Every link MUST point directly to the specific article, blog post, or resource — NEVER link to a homepage, search page, or generic landing page
- For podcast highlights, include direct links to references/papers/tools discussed. If the podcast did not cite specific sources, find and link the most reliable primary source yourself""")

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
    today = datetime.now(_AEST).strftime("%Y-%m-%d")
    return f"# {topic_config['name']} Brief — {today}\n\nNo new items collected for this period."
