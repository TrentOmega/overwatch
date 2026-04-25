import unittest
from unittest.mock import patch

from core.health import check_runtime_health


class HealthChecksTests(unittest.TestCase):
    @patch("core.health._url_reachable", return_value=False)
    @patch("core.health._try_start_local_searxng", return_value=False)
    def test_web_search_without_fallback_is_critical(self, _start_mock, _reachable_mock):
        with patch.dict("os.environ", {"SEARXNG_URL": "http://127.0.0.1:8888"}, clear=True):
            issues = check_runtime_health({"sources": [{"type": "web_search"}]})
        self.assertEqual(issues[0]["severity"], "critical")

    @patch("core.health._url_reachable", return_value=False)
    @patch("core.health._try_start_local_searxng", return_value=False)
    def test_web_search_with_brave_fallback_is_warning(self, _start_mock, _reachable_mock):
        with patch.dict(
            "os.environ",
            {"SEARXNG_URL": "http://127.0.0.1:8888", "BRAVE_SEARCH_API_KEY": "test"},
            clear=True,
        ):
            issues = check_runtime_health({"sources": [{"type": "web_search"}]})
        self.assertEqual(issues[0]["severity"], "warning")

    @patch("importlib.util.find_spec", return_value=None)
    def test_youtube_search_without_yt_dlp_is_critical(self, _find_spec_mock):
        issues = check_runtime_health({"sources": [{"type": "youtube_search"}]})
        self.assertEqual(issues[0]["severity"], "critical")


if __name__ == "__main__":
    unittest.main()
