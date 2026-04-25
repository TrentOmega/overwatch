#!/usr/bin/env python3
"""Overwatch — Intelligence Briefing System"""

import argparse
import os
from datetime import datetime, timezone, timedelta

import yaml

from core.ai import resolve_ai_settings
from core.collector import load_topic, collect, get_last_run, save_last_run
from core.health import check_runtime_health
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


_AEST = timezone(timedelta(hours=10))


def run_topic(slug, global_config, dry_run=False, ai_provider=None, ai_model=None, report_date=None):
    """Run the full pipeline for a single topic."""
    print(f"\n{'='*50}")
    print(f"OVERWATCH — {slug.upper()}")
    print(f"{'='*50}")

    topic_config = load_topic(slug)
    state_dir = global_config.get("state_dir", "state")
    output_dir = global_config.get("output_dir", "output")
    ai_settings = resolve_ai_settings(global_config, provider_override=ai_provider, model_override=ai_model)
    print(f"AI provider: {ai_settings['provider']}" + (f" (model: {ai_settings['model']})" if ai_settings.get("model") else ""))

    health_issues = check_runtime_health(topic_config)
    if health_issues:
        print("\n[0/4] Runtime health checks...")
        for issue in health_issues:
            print(f"  [{issue['severity']}] {issue['message']}")
        if any(issue["severity"] == "critical" for issue in health_issues):
            raise RuntimeError("Critical runtime health checks failed; refusing to generate a degraded brief.")

    # Collect
    print("\n[1/4] Collecting sources...")
    backfill_mode = report_date is not None
    if backfill_mode:
        since, until = _report_window(report_date)
        print(f"  Backfill window: {since.isoformat()} to {until.isoformat()} (AEST report date {report_date.strftime('%Y-%m-%d')})")
    else:
        since = get_last_run(slug, state_dir)
        until = None
        if since:
            print(f"  Filtering items since: {since.isoformat()}")

    items = collect(topic_config, since=since, until=until)
    print(f"  Total items collected: {len(items)}")

    # Cap items to avoid overwhelming the synthesizer
    max_items = global_config.get("max_items", 50)
    if len(items) > max_items:
        items.sort(key=lambda x: x.get("date") or "", reverse=True)
        items = items[:max_items]
        print(f"  Capped to most recent {max_items} items")

    if not items:
        print("  No items from structured sources — the configured AI will research independently")

    # Synthesize
    print("\n[2/4] Synthesizing brief...")
    content = synthesize(items, topic_config, ai_settings=ai_settings, report_date=report_date)
    print(f"  Brief generated ({len(content)} chars)")

    # Render
    print("\n[3/4] Rendering output...")
    date_str = report_date.strftime("%Y-%m-%d") if report_date else datetime.now(_AEST).strftime("%Y-%m-%d")
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
    if not backfill_mode:
        save_last_run(slug, state_dir)
    print("\nDone.")


def main():
    parser = argparse.ArgumentParser(description="Overwatch — Intelligence Briefing System")
    parser.add_argument("--topic", required=True, help="Topic slug to run (or 'all' for all topics)")
    parser.add_argument("--dry-run", action="store_true", help="Collect and synthesize but don't publish")
    parser.add_argument("--list", action="store_true", help="List available topics")
    parser.add_argument("--config", default="config.yaml", help="Path to global config")
    parser.add_argument("--ai-provider", help="AI provider override (for example: claude or codex)")
    parser.add_argument("--model", help="Model override for the selected AI provider")
    parser.add_argument("--report-date", help="Backfill report date in YYYY-MM-DD; collects the prior AEST day and does not update state")
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if args.list:
        for t in list_topics():
            print(f"  {t}")
        return

    global_config = load_global_config(args.config)
    report_date = datetime.strptime(args.report_date, "%Y-%m-%d").replace(tzinfo=_AEST) if args.report_date else None

    if args.topic == "all":
        for slug in list_topics():
            run_topic(slug, global_config, dry_run=args.dry_run, ai_provider=args.ai_provider, ai_model=args.model, report_date=report_date)
    else:
        run_topic(args.topic, global_config, dry_run=args.dry_run, ai_provider=args.ai_provider, ai_model=args.model, report_date=report_date)


def _report_window(report_date):
    """Return the previous-day AEST window for a retrospective report date."""
    day_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start - timedelta(days=1), day_start


if __name__ == "__main__":
    main()
