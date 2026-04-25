import sys
import unittest

from sources.youtube import _yt_dlp_base_cmd


class YoutubeTests(unittest.TestCase):
    def test_yt_dlp_base_command_uses_active_python(self):
        self.assertEqual(_yt_dlp_base_cmd(), [sys.executable, "-m", "yt_dlp"])


if __name__ == "__main__":
    unittest.main()
