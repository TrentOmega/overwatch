import os
import re

import markdown
from jinja2 import Environment, FileSystemLoader

from core.outline import generate_display_outline, generate_slug_outline


def render(content, topic_config, items, date_str, output_dir="output", templates_dir="templates"):
    """Render synthesized content to markdown and HTML files."""
    content = _normalize_brief_content(content)
    slug = topic_config["slug"]
    topic_dir = os.path.join(output_dir, slug)
    os.makedirs(topic_dir, exist_ok=True)

    env = Environment(loader=FileSystemLoader(templates_dir))
    source_names = sorted(set(item["source_name"] for item in items if item.get("source_name")))

    content_html = _md_to_html(content)
    outline_slug = generate_slug_outline(content)
    outline_display = generate_display_outline(content)
    basename = f"{date_str}_{outline_slug}" if outline_slug else date_str

    context = {
        "topic_name": topic_config["name"],
        "date": date_str,
        "content": content,
        "content_html": content_html,
        "outline": outline_display,
        "item_count": len(items),
        "sources": source_names,
    }

    md_path = os.path.join(topic_dir, f"{basename}.md")
    md_template = env.get_template("brief.md.j2")
    with open(md_path, "w") as f:
        f.write(md_template.render(context))

    html_path = os.path.join(topic_dir, f"{basename}.html")
    html_template = env.get_template("brief.html.j2")
    with open(html_path, "w") as f:
        f.write(html_template.render(context))

    print(f"  Rendered: {md_path}")
    print(f"  Rendered: {html_path}")
    return md_path, html_path


def _md_to_html(content):
    """Convert markdown to HTML, auto-linking bare URLs."""
    # Convert bare URLs to clickable links, but skip URLs already inside markdown links
    # Negative lookbehind for ]( and ( to avoid double-wrapping [text](url) or (url)
    content = re.sub(
        r'(?<!\]\()(?<!\()(https?://[^\s<>\)\]]+)',
        r'[\1](\1)',
        content,
    )
    return markdown.markdown(
        content,
        extensions=["tables", "fenced_code", "toc"],
    )


def _normalize_brief_content(content):
    """Apply markdown- and brief-level cleanup before rendering."""
    content = _normalize_markdown_tables(content)
    return _normalize_summary_signals(content)


def _normalize_markdown_tables(content):
    """Insert a separator row for markdown tables when the model omits it."""
    lines = content.splitlines()
    normalized = []

    for index, line in enumerate(lines):
        normalized.append(line)
        if not _starts_table_without_separator(lines, index):
            continue
        normalized.append(_table_separator(line))

    return "\n".join(normalized)


def _normalize_summary_signals(content):
    """Normalize empty summary-table signals to exact NSTR."""
    normalized = []
    for line in content.splitlines():
        if not _is_table_row(line):
            normalized.append(line)
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or not cells[0].isdigit():
            normalized.append(line)
            continue

        if _is_nstr_signal(cells[2]):
            cells[2] = "NSTR"
            line = f"| {cells[0]} | {cells[1]} | {cells[2]} |"

        normalized.append(line)

    return "\n".join(normalized)


def _starts_table_without_separator(lines, index):
    line = lines[index]
    if not _is_table_row(line):
        return False
    if index > 0 and (_is_table_row(lines[index - 1]) or _is_separator_row(lines[index - 1])):
        return False
    if index + 1 >= len(lines):
        return False
    next_line = lines[index + 1]
    return _is_table_row(next_line) and not _is_separator_row(next_line)


def _is_table_row(line):
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def _is_separator_row(line):
    stripped = line.strip().strip("|")
    if not stripped:
        return False
    cells = [cell.strip() for cell in stripped.split("|")]
    return all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _table_separator(line):
    column_count = max(len(line.strip().strip("|").split("|")), 1)
    return "|" + "|".join("---" for _ in range(column_count)) + "|"


def _is_nstr_signal(signal):
    normalized = re.sub(r"\s+", " ", signal.strip().rstrip(".")).lower()
    if normalized == "nstr":
        return True

    patterns = (
        r"no .+ confirmed(?: in supplied material)?",
        r"no .+ provided",
        r"no .+ identified",
        r"no .+ reported",
    )
    return any(re.fullmatch(pattern, normalized) for pattern in patterns)
