from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from x2telegram.cli import _check, _check_coding_agent, _parser
from x2telegram.config import load_config


class CliTests(unittest.TestCase):
    def test_count_override_is_parsed(self) -> None:
        args = _parser().parse_args(["run", "--count", "7", "--dry-run", "--quiet"])
        self.assertEqual(args.count, 7)
        self.assertTrue(args.quiet)

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

    def test_check_rejects_old_codex_missing_security_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt_path = root / "prompt.md"
            prompt_path.write_text("Summarize.", encoding="utf-8")
            config_path = root / "config.toml"
            config_path.write_text(
                '[summary]\nprovider = "coding_agent"\nagent = "codex"\n'
                'prompt_file = "prompt.md"\n',
                encoding="utf-8",
            )
            results = [
                subprocess.CompletedProcess(["bird", "--version"], 0, "0.8.0", ""),
                subprocess.CompletedProcess(["bird", "check"], 0, "ready", ""),
                subprocess.CompletedProcess(
                    ["codex", "exec", "--help"], 0, "--sandbox --ephemeral", ""
                ),
            ]
            with patch.dict(os.environ, {"AUTH_TOKEN": "secret", "CT0": "secret"}, clear=True):
                with patch(
                    "x2telegram.cli.find_executable",
                    side_effect=lambda executable: f"/usr/bin/{executable}",
                ):
                    with patch("x2telegram.cli.subprocess.run", side_effect=results):
                        with self.assertRaisesRegex(RuntimeError, "--ignore-user-config"):
                            _check(
                                argparse.Namespace(
                                    config=str(config_path), require_telegram=False
                                )
                            )

    def test_check_reports_explicit_codex_model_and_reasoning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt_path = root / "prompt.md"
            prompt_path.write_text("Summarize.", encoding="utf-8")
            config_path = root / "config.toml"
            config_path.write_text(
                '[summary]\nprovider = "coding_agent"\nagent = "codex"\n'
                'model = "gpt-5.6-terra"\nreasoning_effort = "medium"\n'
                'prompt_file = "prompt.md"\n',
                encoding="utf-8",
            )
            help_text = " ".join(
                (
                    "--config",
                    "--strict-config",
                    "--ephemeral",
                    "--sandbox",
                    "--skip-git-repo-check",
                    "--ignore-user-config",
                    "--output-last-message",
                )
            )
            with patch("x2telegram.cli.find_executable", return_value="codex"):
                with patch(
                    "x2telegram.cli.subprocess.run",
                    return_value=subprocess.CompletedProcess(
                        ["codex", "exec", "--help"], 0, help_text, ""
                    ),
                ):
                    status = _check_coding_agent(load_config(config_path))

            self.assertIn("model: gpt-5.6-terra", status)
            self.assertIn("reasoning: medium", status)

    def test_check_explains_developer_oauth_is_not_session_cookie_auth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            auth_path = root / "x-oauth.env"
            auth_path.write_text("CONSUMER_KEY=placeholder\n", encoding="utf-8")
            config_path = root / "config.toml"
            config_path.write_text(
                '[source]\nauth_env_file = "x-oauth.env"\n'
                '[summary]\nprovider = "digest"\n',
                encoding="utf-8",
            )
            results = [
                subprocess.CompletedProcess(["bird", "--version"], 0, "0.8.0", ""),
                subprocess.CompletedProcess(["bird", "check"], 1, "not ready", ""),
            ]
            with patch.dict(os.environ, {}, clear=True):
                with patch("x2telegram.cli.find_executable", return_value="/usr/bin/bird"):
                    with patch("x2telegram.cli.subprocess.run", side_effect=results):
                        with self.assertRaisesRegex(RuntimeError, "not browser session cookies"):
                            _check(
                                argparse.Namespace(
                                    config=str(config_path), require_telegram=False
                                )
                            )

    def test_check_rejects_telegram_sample_placeholders_without_network_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_path = root / ".env"
            env_path.write_text(
                "TELEGRAM_BOT_TOKEN=replace-me\nTELEGRAM_CHAT_ID=replace-me\n",
                encoding="utf-8",
            )
            config_path = root / "config.toml"
            config_path.write_text('[summary]\nprovider = "digest"\n', encoding="utf-8")
            results = [
                subprocess.CompletedProcess(["bird", "--version"], 0, "0.8.0", ""),
                subprocess.CompletedProcess(["bird", "check"], 0, "ready", ""),
            ]
            with patch.dict(os.environ, {}, clear=True):
                with patch("x2telegram.cli.find_executable", return_value="bird.cmd"):
                    with patch("x2telegram.cli.subprocess.run", side_effect=results):
                        with patch("x2telegram.cli.probe_telegram_destination") as probe:
                            result = _check(
                                argparse.Namespace(
                                    config=str(config_path), require_telegram=True
                                )
                            )

            self.assertEqual(result, 2)
            probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
