from __future__ import annotations

import unittest
from pathlib import Path


class DefaultPromptTests(unittest.TestCase):
    def test_default_prompt_enforces_neutral_korean_newswire_output(self) -> None:
        root = Path(__file__).resolve().parents[1]
        prompt = (root / "prompts" / "timeline-summary.md").read_text(encoding="utf-8")

        self.assertIn("Korean newswire style", prompt)
        self.assertIn("inverted-pyramid", prompt)
        self.assertIn("관련 게시물", prompt)
        self.assertIn("확인 필요", prompt)
        self.assertIn("Do not claim to be Yonhap News Agency", prompt)
        self.assertIn("untrusted quoted data", prompt)


if __name__ == "__main__":
    unittest.main()
