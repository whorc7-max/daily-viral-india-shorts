import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.fetch_gemini_keys import main


class FetchKeysTests(unittest.TestCase):
    def test_main_masks_keys_and_writes_them_to_github_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "github-env"
            with (
                patch.dict(os.environ, {
                    "GITHUB_ENV": str(env_path),
                    "KEY_OUTPUT_PREFIX": "GEMINI",
                }),
                patch("scripts.fetch_gemini_keys._configured_keys", return_value=["key-one", "key-two"]),
                patch("builtins.print") as print_command,
            ):
                main()

            self.assertEqual(
                env_path.read_text(encoding="utf-8"),
                "GEMINI_API_KEY=key-one\nGEMINI_API_KEYS=key-one,key-two\n",
            )
            self.assertEqual(
                [call.args[0] for call in print_command.call_args_list],
                ["::add-mask::key-one", "::add-mask::key-two"],
            )

    def test_main_refuses_to_print_keys_outside_github_actions(self):
        with (
            patch.dict(os.environ, {"GITHUB_ENV": "", "KEY_OUTPUT_PREFIX": "GEMINI"}),
            patch("scripts.fetch_gemini_keys._configured_keys", return_value=["secret-key"]),
        ):
            with self.assertRaisesRegex(RuntimeError, "refusing to print API keys"):
                main()


if __name__ == "__main__":
    unittest.main()
