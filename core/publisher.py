import glob
import os
import re
import subprocess

import yaml
from jinja2 import Environment, FileSystemLoader


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

    headlines = re.findall(r'\*\*(.+?)\*\*', content)
    # Skip short, generic, meta, and summary-table category entries
    headlines = [
        h for h in headlines
        if len(h) > 5
        and not h.startswith("Why")
        and not h.startswith("Classification")
        and not h.startswith("Date")
        and not h.startswith("Link")
        and not h.startswith("Summary")
        and not h.startswith("Key")
        and not h.startswith("Top")
        and not re.match(r'^\d+\.', h)  # skip numbered summary table entries
    ]

    selected = []
    seen = set()
    for h in headlines:
        key = h.lower()
        if key in seen:
            continue
        seen.add(key)
        # Shorten long headlines at a natural break (colon, dash, comma)
        short = _shorten_headline(h, max_len=40)
        if short:
            selected.append(short)
        if len(selected) >= max_items:
            break

    if not selected:
        return ""

    # Build display string; reduce topic count if result is too long
    for count in (len(selected), 2, 1):
        result = "; ".join(selected[:count])
        if len(result) <= 90:
            return result

    return selected[0][:90]


_WEAK_ENDINGS = {'a', 'an', 'the', 'to', 'of', 'in', 'on', 'for', 'and', 'or', 'with', 'by', 'at', 'its'}


def _trim_weak_ending(text):
    """Strip trailing articles, prepositions, and conjunctions."""
    words = text.rsplit(' ', 1)
    if len(words) == 2 and words[1].lower() in _WEAK_ENDINGS:
        return words[0]
    return text


def _shorten_headline(headline, max_len=40):
    """Shorten a headline at a natural break point, preserving meaning."""
    if len(headline) <= max_len:
        return headline

    # Try splitting at natural break points
    for sep in (':', ' \u2014 ', ' \u2013 ', ' — ', ' | ', ' - ', ' (', ' \u201c', ' "'):
        if sep in headline:
            first_part = _trim_weak_ending(headline.split(sep)[0].strip())
            if 10 < len(first_part) <= max_len:
                return first_part

    # Fall back to truncating at last meaningful word within limit
    truncated = headline[:max_len]
    last_space = truncated.rfind(' ')
    if last_space > 15:
        return _trim_weak_ending(truncated[:last_space])

    return truncated


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
