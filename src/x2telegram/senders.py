from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol


class Sender(Protocol):
    def send(self, text: str) -> int: ...


_TELEGRAM_PLACEHOLDERS = {
    "change-me",
    "changeme",
    "replace-me",
    "replace_me",
    "your-bot-token",
    "your-chat-id",
}


def _is_placeholder(value: str | None) -> bool:
    normalized = (value or "").strip().casefold()
    return (
        not normalized
        or normalized in _TELEGRAM_PLACEHOLDERS
        or normalized.startswith(("replace-", "replace_", "your-", "your_", "여기에_"))
    )


def telegram_credentials_are_configured(bot_token: str | None, chat_id: str | None) -> bool:
    return not _is_placeholder(bot_token) and not _is_placeholder(chat_id)


def _telegram_api_call(
    bot_token: str, method: str, parameters: dict[str, object], *, timeout: int = 15
) -> object:
    endpoint = f"https://api.telegram.org/bot{bot_token}/{method}"
    body = urllib.parse.urlencode(parameters).encode("utf-8")
    request = urllib.request.Request(endpoint, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Telegram API {method} failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Telegram API {method} failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Telegram API {method} returned invalid JSON") from exc
    if not isinstance(payload, dict) or not payload.get("ok"):
        description = (
            str(payload.get("description") or "unknown Telegram API error")
            if isinstance(payload, dict)
            else "invalid Telegram API response"
        )
        raise RuntimeError(f"Telegram API {method} rejected the request: {description}")
    return payload.get("result")


def _safe_display(value: object, fallback: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return fallback
    return text[:97] + "…" if len(text) > 100 else text


def probe_telegram_destination(bot_token: str, chat_id: str) -> str:
    if not telegram_credentials_are_configured(bot_token, chat_id):
        raise ValueError("Telegram credentials are not configured; replace the sample values")

    bot = _telegram_api_call(bot_token, "getMe", {})
    chat = _telegram_api_call(bot_token, "getChat", {"chat_id": chat_id})
    if not isinstance(bot, dict) or not isinstance(chat, dict):
        raise RuntimeError("Telegram API returned an invalid bot or destination record")

    bot_username = _safe_display(bot.get("username"), "bot")
    bot_label = f"@{bot_username}" if bot.get("username") else bot_username
    chat_type = _safe_display(chat.get("type"), "chat")
    if chat.get("title"):
        destination = _safe_display(chat.get("title"), "Telegram destination")
    elif chat.get("username"):
        destination = f"@{_safe_display(chat.get('username'), 'destination')}"
    else:
        first_name = _safe_display(chat.get("first_name"), "private chat")
        destination = first_name
    return f"{destination} ({chat_type}) via {bot_label}"


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
        if not telegram_credentials_are_configured(self.bot_token, self.chat_id):
            raise ValueError("Telegram credentials are not configured; replace the sample values")

    def send(self, text: str) -> int:
        chunks = split_telegram_text(text)
        for chunk in chunks:
            _telegram_api_call(
                self.bot_token,
                "sendMessage",
                {
                    "chat_id": self.chat_id,
                    "text": chunk,
                    "disable_web_page_preview": str(self.disable_web_page_preview).lower(),
                },
                timeout=30,
            )
        return len(chunks)
