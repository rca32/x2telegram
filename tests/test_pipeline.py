from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2telegram.pipeline import Pipeline
from x2telegram.senders import Sender, split_telegram_text
from x2telegram.sources import JsonFileTimelineSource
from x2telegram.state import SeenTweetStore
from x2telegram.summarizers import DigestSummarizer


FIXTURE = Path(__file__).parent / "fixtures" / "timeline.json"


class RecordingSender:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, text: str) -> int:
        self.messages.append(text)
        return 1


class FailingSender:
    def send(self, text: str) -> int:
        raise RuntimeError("simulated delivery failure")


class PipelineTests(unittest.TestCase):
    def make_pipeline(self, state_path: Path, sender: Sender | None = None) -> Pipeline:
        return Pipeline(
            source=JsonFileTimelineSource(FIXTURE),
            summarizer=DigestSummarizer(
                title="Test digest", max_items=2, max_chars_per_item=80, keywords=["inflation", "AI"]
            ),
            sender=sender,
            state=SeenTweetStore(state_path),
        )

    def test_dry_run_does_not_write_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "seen.json"
            result = self.make_pipeline(state_path).run(dry_run=True)
            self.assertEqual(result.new_count, 3)
            self.assertIn("Topics:", result.digest)
            self.assertFalse(state_path.exists())

    def test_successful_send_updates_state_and_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "seen.json"
            sender = RecordingSender()
            first = self.make_pipeline(state_path, sender).run()
            second = self.make_pipeline(state_path, sender).run()
            self.assertEqual(first.new_count, 3)
            self.assertEqual(second.new_count, 0)
            self.assertEqual(len(sender.messages), 1)

    def test_failed_send_does_not_write_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "seen.json"
            with self.assertRaisesRegex(RuntimeError, "simulated delivery failure"):
                self.make_pipeline(state_path, FailingSender()).run()
            self.assertFalse(state_path.exists())

    def test_account_allowlist_filters_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self.make_pipeline(Path(directory) / "seen.json")
            pipeline.accounts = {"macrodesk"}
            result = pipeline.run(dry_run=True)
            self.assertEqual(result.matched_count, 2)


class TelegramSplitTests(unittest.TestCase):
    def test_split_prefers_newlines_and_preserves_text(self) -> None:
        chunks = split_telegram_text("alpha beta\ngamma delta", max_length=12)
        self.assertEqual(chunks, ["alpha beta", "gamma delta"])


if __name__ == "__main__":
    unittest.main()
