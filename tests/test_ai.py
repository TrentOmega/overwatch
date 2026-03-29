import unittest
from unittest.mock import patch, MagicMock

from core.ai import resolve_ai_settings, run_prompt


class ResolveAISettingsTests(unittest.TestCase):
    def test_default_provider_is_codex(self):
        settings = resolve_ai_settings({})
        self.assertEqual(settings["provider"], "codex")
        self.assertEqual(settings["command"][0], "codex")

    @patch.dict("os.environ", {"OVERWATCH_AI_PROVIDER": "claude"}, clear=False)
    def test_env_can_switch_provider(self):
        settings = resolve_ai_settings({})
        self.assertEqual(settings["provider"], "claude")
        self.assertEqual(settings["command"][:2], ["claude", "-p"])

    def test_config_can_define_custom_provider(self):
        settings = resolve_ai_settings(
            {
                "ai": {
                    "provider": "custom",
                    "providers": {
                        "custom": {
                            "command": ["my-ai", "--stdin"],
                            "model_flag": "--model",
                            "working_dir": "/tmp",
                        }
                    },
                }
            }
        )
        self.assertEqual(settings["provider"], "custom")
        self.assertEqual(settings["command"], ["my-ai", "--stdin"])


class RunPromptTests(unittest.TestCase):
    @patch("core.ai.subprocess.run")
    def test_stdout_mode_returns_stdout(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "hello"
        mock_run.return_value.stderr = ""

        result = run_prompt(
            "prompt",
            {
                "provider": "test",
                "command": ["test-ai", "-"],
                "timeout_seconds": 5,
                "working_dir": "/tmp",
                "strip_env": [],
                "output_mode": "stdout",
            },
        )

        self.assertEqual(result, "hello")

    @patch("core.ai.subprocess.run")
    def test_file_mode_places_output_flag_before_stdin_arg(self, mock_run):
        def fake_run(cmd, **kwargs):
            output_path = cmd[cmd.index("--output-last-message") + 1]
            with open(output_path, "w") as f:
                f.write("from-file")
            completed = MagicMock()
            completed.returncode = 0
            completed.stdout = ""
            completed.stderr = ""
            return completed

        mock_run.side_effect = fake_run

        result = run_prompt(
            "prompt",
            {
                "provider": "codex",
                "command": ["codex", "exec", "--color", "never", "-"],
                "model_flag": "--model",
                "model": "gpt-5",
                "timeout_seconds": 5,
                "working_dir": "/tmp",
                "strip_env": [],
                "output_mode": "file",
                "output_file_flag": "--output-last-message",
            },
        )

        called_cmd = mock_run.call_args.args[0]
        self.assertEqual(called_cmd[-1], "-")
        self.assertLess(called_cmd.index("--output-last-message"), called_cmd.index("-"))
        self.assertEqual(result, "from-file")


if __name__ == "__main__":
    unittest.main()
