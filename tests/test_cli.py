from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from x2telegram.cli import _check, _parser


class CliTests(unittest.TestCase):
    def test_count_override_is_parsed(self) -> None:
        args = _parser().parse_args(["run", "--count", "7", "--dry-run"])
        self.assertEqual(args.count, 7)

    def test_check_distinguishes_preview_from_delivery_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text('[summary]\nprovider = "digest"\n', encoding="utf-8")
            results = [
                subprocess.CompletedProcess(["bird", "--version"], 0, "0.8.0", ""),
                subprocess.CompletedProcess(["bird", "check"], 0, "ready", ""),
            ] * 2
            with patch.dict(os.environ, {}, clear=True):
                with patch("x2telegram.cli.find_executable", return_value="bird.cmd"):
                    with patch("x2telegram.cli.subprocess.run", side_effect=results):
                        preview = _check(
                            argparse.Namespace(config=str(config_path), require_telegram=False)
                        )
                        delivery = _check(
                            argparse.Namespace(config=str(config_path), require_telegram=True)
                        )

            self.assertEqual(preview, 0)
            self.assertEqual(delivery, 2)


if __name__ == "__main__":
    unittest.main()
