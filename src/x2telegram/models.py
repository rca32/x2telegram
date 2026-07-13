from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, slots=True)
class Tweet:
    id: str
    username: str
    author_name: str
    text: str
    created_at: str = ""
    reply_count: int = 0
    retweet_count: int = 0
    like_count: int = 0

    @property
    def url(self) -> str:
        return f"https://x.com/{self.username}/status/{self.id}"

    @property
    def created_datetime(self) -> datetime | None:
        if not self.created_at:
            return None
        try:
            return datetime.strptime(self.created_at, "%a %b %d %H:%M:%S %z %Y")
        except ValueError:
            try:
                return datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            except ValueError:
                return None

    @classmethod
    def from_bird(cls, payload: Mapping[str, Any]) -> "Tweet":
        author = payload.get("author")
        if not isinstance(author, Mapping):
            author = {}

        tweet_id = str(payload.get("id") or "").strip()
        username = str(author.get("username") or payload.get("username") or "").strip().lstrip("@")
        if not tweet_id or not username:
            raise ValueError("bird tweet is missing id or author.username")

        return cls(
            id=tweet_id,
            username=username,
            author_name=str(author.get("name") or payload.get("authorName") or username).strip(),
            text=str(payload.get("text") or "").strip(),
            created_at=str(payload.get("createdAt") or "").strip(),
            reply_count=_integer(payload.get("replyCount")),
            retweet_count=_integer(payload.get("retweetCount")),
            like_count=_integer(payload.get("likeCount")),
        )

