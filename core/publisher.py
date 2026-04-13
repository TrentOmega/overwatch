import glob
import os
import re
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader

from core.outline import generate_display_outline

def _display_outline(html_path, max_items=3):
    """Extract a display-friendly outline from the brief's markdown content.

    Reads the .md sibling of the HTML file and pulls properly-capitalised
    headlines. Returns up to max_items topics, dropping down to fewer if
    compression would make them nonsensical.
    """
    md_path = re.sub(r'\.html$', '.md', html_path)
    if not os.path.isfile(md_path):
        return ""

    with open(md_path) as f:
        content = f.read()

    return generate_display_outline(content, max_items=max_items, max_len=90)


def _generate_index(output_dir="output", topics_dir="topics"):
    """Scan output/ for briefs and generate an index.html at repo root."""
    # Load topic names from YAML files
    topic_names = {}
    if os.path.isdir(topics_dir):
        for fname in os.listdir(topics_dir):
            if fname.endswith(".yaml") and not fname.startswith("_"):
                slug = fname.replace(".yaml", "")
                try:
                    with open(os.path.join(topics_dir, fname)) as f:
                        tc = yaml.safe_load(f)
                    topic_names[slug] = tc.get("name", slug.replace("-", " ").title())
                except Exception:
                    topic_names[slug] = slug.replace("-", " ").title()

    # Scan output/ for {slug}/{date}[_{outline}].html files
    topics = {}
    html_files = glob.glob(os.path.join(output_dir, "*", "*.html"))
    for path in html_files:
        rel = os.path.relpath(path)
        parts = rel.split(os.sep)
        if len(parts) >= 2:
            slug = parts[-2]
            filename = os.path.splitext(parts[-1])[0]
            date = filename[:10]  # YYYY-MM-DD
            # Extract display outline from brief content (proper capitalisation)
            outline = _display_outline(path)
            topics.setdefault(slug, []).append({
                "date": date,
                "outline": outline,
                "path": rel,
            })

    # Sort briefs newest-first within each topic
    for slug in topics:
        topics[slug].sort(key=lambda b: b["date"], reverse=True)

    # Build template data sorted by topic name
    topics_data = []
    for slug in sorted(topics.keys()):
        name = topic_names.get(slug, slug.replace("-", " ").title())
        topics_data.append({
            "name": name,
            "briefs": topics[slug],
        })

    # Render index.html
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("index.html.j2")
    html = template.render(topics=topics_data)

    index_path = "index.html"
    with open(index_path, "w") as f:
        f.write(html)

    print(f"  Generated {index_path} ({len(topics_data)} topics)")
    return index_path


def publish(files, topic_config, date_str, auto_push=False):
    """Git add, commit, and optionally push the generated brief files."""
    slug = topic_config["slug"]
    name = topic_config["name"]

    # Regenerate index page
    index_path = _generate_index()

    for f in [*files, index_path]:
        subprocess.run(["git", "add", f], check=True)

    message = f"brief: {name} {date_str}"
    subprocess.run(["git", "commit", "-m", message], check=True)
    print(f"  Committed: {message}")

    if auto_push:
        subprocess.run(["git", "push"], check=True)
        print("  Pushed to remote")
