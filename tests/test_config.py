from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2telegram.config import load_config, read_list


class ConfigTests(unittest.TestCase):
    def test_relative_paths_are_based_on_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.toml"
            config_path.write_text(
                '[source]\naccounts_file = "accounts.txt"\n'
                '[summary]\nkeywords_file = "keywords.txt"\n'
                '[state]\npath = "data/seen.json"\n',
                encoding="utf-8",
            )
            config = load_config(config_path)
            self.assertEqual(config.source.accounts_file, root / "accounts.txt")
            self.assertEqual(config.summary.keywords_file, root / "keywords.txt")
            self.assertEqual(config.state.path, root / "data" / "seen.json")

    def test_configured_missing_list_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing-accounts.txt"
            with self.assertRaises(FileNotFoundError):
                read_list(missing)


if __name__ == "__main__":
    unittest.main()
