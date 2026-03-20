import os
import re

import markdown
from jinja2 import Environment, FileSystemLoader


def _generate_byline(content, max_items=3, max_len=60):
    """Extract a short slug-friendly byline from the first bold headlines in the content."""
    headlines = re.findall(r'\*\*(.+?)\*\*', content)
    # Skip very short or generic matches
    headlines = [h for h in headlines if len(h) > 5 and not h.startswith("Why")]
    slugs = []
    seen = set()
    for h in headlines:
        if len(slugs) >= max_items:
            break
        # Slugify: lowercase, keep alphanum and hyphens, collapse whitespace
        s = re.sub(r'[^a-z0-9]+', '-', h.lower()).strip('-')
        # Truncate individual slugs
        s = s[:25].rstrip('-')
        if s and s not in seen:
            seen.add(s)
            slugs.append(s)
    byline = '_'.join(slugs)
    return byline[:max_len].rstrip('-_') if byline else ""


def render(content, topic_config, items, date_str, output_dir="output", templates_dir="templates"):
    """Render synthesized content to markdown and HTML files."""
    slug = topic_config["slug"]
    topic_dir = os.path.join(output_dir, slug)
    os.makedirs(topic_dir, exist_ok=True)

    env = Environment(loader=FileSystemLoader(templates_dir))
    source_names = sorted(set(item["source_name"] for item in items if item.get("source_name")))

    content_html = _md_to_html(content)
    byline = _generate_byline(content)
    basename = f"{date_str}_{byline}" if byline else date_str

    context = {
        "topic_name": topic_config["name"],
        "date": date_str,
        "content": content,
        "content_html": content_html,
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
        extensions=["tables", "fenced_code"],
    )
