from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol


class Sender(Protocol):
    def send(self, text: str) -> int: ...


def split_telegram_text(text: str, max_length: int = 3900) -> list[str]:
    if max_length < 1:
        raise ValueError("max_length must be positive")
    chunks: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_length:
        split_at = remaining.rfind("\n", 0, max_length + 1)
        if split_at < 1:
            split_at = max_length
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


class TelegramSender:
    def __init__(
        self,
        *,
        bot_token: str | None = None,
        chat_id: str | None = None,
        disable_web_page_preview: bool = True,
    ) -> None:
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.disable_web_page_preview = disable_web_page_preview
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is not set")

    def send(self, text: str) -> int:
        chunks = split_telegram_text(text)
        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        for chunk in chunks:
            body = urllib.parse.urlencode(
                {
                    "chat_id": self.chat_id,
                    "text": chunk,
                    "disable_web_page_preview": str(self.disable_web_page_preview).lower(),
                }
            ).encode("utf-8")
            request = urllib.request.Request(endpoint, data=body, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"Telegram API request failed with HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"Telegram API request failed: {exc.reason}") from exc
            if not result.get("ok"):
                description = str(result.get("description") or "unknown Telegram API error")
                raise RuntimeError(f"Telegram rejected the message: {description}")
        return len(chunks)

