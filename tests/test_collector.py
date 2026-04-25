import unittest
from datetime import datetime, timezone

from core.collector import _filter_items_by_date


class CollectorTests(unittest.TestCase):
    def test_filter_drops_undated_web_search_items_for_fixed_backfill_window(self):
        items = [
            {
                "title": "Undated GPT-5.5 search hit",
                "source_type": "web_search",
                "date": "",
            }
        ]

        filtered = _filter_items_by_date(
            items,
            since=datetime(2026, 4, 21, tzinfo=timezone.utc),
            until=datetime(2026, 4, 22, tzinfo=timezone.utc),
        )

        self.assertEqual(filtered, [])

    def test_filter_keeps_undated_non_search_items_for_fixed_backfill_window(self):
        items = [
            {
                "title": "Undated RSS item",
                "source_type": "rss",
                "date": "",
            }
        ]

        filtered = _filter_items_by_date(
            items,
            since=datetime(2026, 4, 21, tzinfo=timezone.utc),
            until=datetime(2026, 4, 22, tzinfo=timezone.utc),
        )

        self.assertEqual(filtered, items)


if __name__ == "__main__":
    unittest.main()
