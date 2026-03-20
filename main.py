#!/usr/bin/env python3
"""Overwatch — Intelligence Briefing System"""

import argparse
import os
import sys
from datetime import datetime, timezone

import yaml

from core.collector import load_topic, collect, get_last_run, save_last_run
from core.synthesizer import synthesize
from core.renderer import render
from core.publisher import publish


def load_global_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def list_topics(topics_dir="topics"):
    """List available topic slugs."""
    topics = []
    for f in sorted(os.listdir(topics_dir)):
        if f.endswith(".yaml") and not f.startswith("_"):
            topics.append(f.replace(".yaml", ""))
    return topics


def run_topic(slug, global_config, dry_run=False):
    """Run the full pipeline for a single topic."""
    print(f"\n{'='*50}")
    print(f"OVERWATCH — {slug.upper()}")
    print(f"{'='*50}")

    topic_config = load_topic(slug)
    state_dir = global_config.get("state_dir", "state")
    output_dir = global_config.get("output_dir", "output")
    model = global_config.get("model")

    # Collect
    print("\n[1/4] Collecting sources...")
    since = get_last_run(slug, state_dir)
    if since:
        print(f"  Filtering items since: {since.isoformat()}")
    items = collect(topic_config, since=since)
    print(f"  Total items collected: {len(items)}")

    # Cap items to avoid overwhelming the synthesizer
    max_items = global_config.get("max_items", 50)
    if len(items) > max_items:
        items.sort(key=lambda x: x.get("date") or "", reverse=True)
        items = items[:max_items]
        print(f"  Capped to most recent {max_items} items")

    if not items:
        print("  No items from structured sources — Claude will research independently")

    # Synthesize
    print("\n[2/4] Synthesizing brief...")
    content = synthesize(items, topic_config, model=model)
    print(f"  Brief generated ({len(content)} chars)")

    # Render
    print("\n[3/4] Rendering output...")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md_path, html_path = render(content, topic_config, items, date_str, output_dir)

    if dry_run:
        print("\n[4/4] Dry run — skipping publish")
        print(f"\n  Preview: {md_path}")
        return

    # Publish
    print("\n[4/4] Publishing...")
    auto_push = global_config.get("publisher", {}).get("auto_push", False)
    publish([md_path, html_path], topic_config, date_str, auto_push=auto_push)

    # Save state
    save_last_run(slug, state_dir)
    print("\nDone.")


def main():
    parser = argparse.ArgumentParser(description="Overwatch — Intelligence Briefing System")
    parser.add_argument("--topic", required=True, help="Topic slug to run (or 'all' for all topics)")
    parser.add_argument("--dry-run", action="store_true", help="Collect and synthesize but don't publish")
    parser.add_argument("--list", action="store_true", help="List available topics")
    parser.add_argument("--config", default="config.yaml", help="Path to global config")
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if args.list:
        for t in list_topics():
            print(f"  {t}")
        return

    global_config = load_global_config(args.config)

    if args.topic == "all":
        for slug in list_topics():
            run_topic(slug, global_config, dry_run=args.dry_run)
    else:
        run_topic(args.topic, global_config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
