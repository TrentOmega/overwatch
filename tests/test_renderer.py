import unittest

from core.renderer import _md_to_html, _normalize_brief_content, _normalize_markdown_tables


class MarkdownTableNormalizationTests(unittest.TestCase):
    def test_inserts_separator_when_model_omits_it(self):
        content = "\n".join([
            "# Brief",
            "",
            "| # | Category | Signal |",
            "| 1 | [Category](#category) | Something happened |",
            "| 2 | [Other](#other) | NSTR |",
        ])

        normalized = _normalize_markdown_tables(content)

        self.assertIn("|---|---|---|", normalized)
        self.assertEqual(normalized.count("|---|---|---|"), 1)

    def test_preserves_existing_separator_row(self):
        content = "\n".join([
            "| # | Category | Signal |",
            "|---|---|---|",
            "| 1 | [Category](#category) | Something happened |",
        ])

        normalized = _normalize_markdown_tables(content)

        self.assertEqual(normalized.count("|---|---|---|"), 1)

    def test_html_conversion_renders_normalized_table(self):
        content = "\n".join([
            "| # | Category | Signal |",
            "| 1 | [Category](#category) | Something happened |",
        ])

        html = _md_to_html(_normalize_markdown_tables(content))

        self.assertIn("<table>", html)
        self.assertIn("<th>#</th>", html)

    def test_normalizes_empty_summary_signals_to_nstr(self):
        content = "\n".join([
            "# Brief",
            "",
            "| # | Category | Signal |",
            "| 1 | [Category](#category) | No major lab release confirmed in supplied material |",
            "| 2 | [Other](#other) | No specific high-signal posts provided |",
            "",
            "## 1. Category",
            "NSTR",
        ])

        normalized = _normalize_brief_content(content)

        self.assertIn("| 1 | [Category](#category) | NSTR |", normalized)
        self.assertIn("| 2 | [Other](#other) | NSTR |", normalized)


if __name__ == "__main__":
    unittest.main()
