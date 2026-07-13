from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from x2telegram.senders import (
    TelegramSender,
    probe_telegram_destination,
    telegram_credentials_are_configured,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class TelegramCredentialTests(unittest.TestCase):
    def test_sample_placeholders_are_not_configured(self) -> None:
        self.assertFalse(telegram_credentials_are_configured("replace-me", "replace-me"))
        self.assertFalse(
            telegram_credentials_are_configured("여기에_bot_token", "여기에_chat_id")
        )
        with self.assertRaisesRegex(ValueError, "sample values"):
            TelegramSender(bot_token="replace-me", chat_id="replace-me")

    def test_probe_returns_safe_destination_without_raw_chat_id(self) -> None:
        responses = [
            FakeResponse({"ok": True, "result": {"username": "summary_bot"}}),
            FakeResponse(
                {
                    "ok": True,
                    "result": {"id": -100123456, "type": "channel", "title": "Daily Brief"},
                }
            ),
        ]
        with patch("x2telegram.senders.urllib.request.urlopen", side_effect=responses):
            label = probe_telegram_destination("123:real-looking-token", "-100123456")

        self.assertEqual(label, "Daily Brief (channel) via @summary_bot")
        self.assertNotIn("100123456", label)


if __name__ == "__main__":
    unittest.main()
