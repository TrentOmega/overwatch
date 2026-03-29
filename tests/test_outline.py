import unittest

from core.outline import generate_display_outline, generate_slug_outline


SAMPLE_CONTENT = """# AI Daily Brief — 2026-03-28

| # | Category | Signal |
|---|---|---|
| 1 | [New LLM Versions / Major AI Lab Tools](#1-new-llm-versions--major-ai-lab-tools) | NSTR |
| 2 | [Major Financial AI Company News](#2-major-financial-ai-company-news) | Aetherflux is reportedly raising a large round for AI-oriented orbital compute infrastructure. |
| 3 | [Major AI Data Center News](#3-major-ai-data-center-news) | Microsoft is taking over a major Texas AI campus expansion tied to a 900MW power plant. |

## 2. Major Financial AI Company News
- 2026-03-27 | [Orbital Data-Center Startup Aetherflux Raising New Financing at $2 Billion Valuation](https://example.com) | Example summary.
"""


class OutlineTests(unittest.TestCase):
    def test_generates_slug_from_summary_signals(self):
        outline = generate_slug_outline(SAMPLE_CONTENT)
        self.assertIn("aetherflux", outline)
        self.assertIn("microsoft", outline)

    def test_generates_display_outline_from_summary_signals(self):
        outline = generate_display_outline(SAMPLE_CONTENT)
        self.assertIn("Aetherflux", outline)
        self.assertIn("Microsoft", outline)

    def test_ignores_pseudo_nstr_summary_signals(self):
        content = """# AI Daily Brief — 2026-03-30

| # | Category | Signal |
|---|---|---|
| 1 | [New LLM Versions / Major AI Lab Tools](#1-new-llm-versions--major-ai-lab-tools) | No major lab release confirmed in supplied material |
| 2 | [Major Financial AI Company News](#2-major-financial-ai-company-news) | China Moonshot AI exploring Hong Kong listing and new raise |
| 3 | [Major AI Data Center News](#3-major-ai-data-center-news) | Meta funding power build-out for Louisiana AI campus |
"""

        outline = generate_display_outline(content)

        self.assertIn("China Moonshot", outline)
        self.assertIn("Meta funding", outline)
        self.assertNotIn("No major lab release confirmed", outline)


if __name__ == "__main__":
    unittest.main()
