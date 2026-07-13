from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Protocol, Sequence

from .models import Tweet


class Summarizer(Protocol):
    def summarize(self, tweets: Sequence[Tweet]) -> str: ...


def _compact(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)].rstrip() + "…"


class DigestSummarizer:
    def __init__(
        self,
        *,
        title: str,
        max_items: int,
        max_chars_per_item: int,
        keywords: Sequence[str] = (),
    ) -> None:
        self.title = title
        self.max_items = max_items
        self.max_chars_per_item = max_chars_per_item
        self.keywords = tuple(dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip()))

    def _hits(self, tweet: Tweet) -> list[str]:
        lowered = tweet.text.casefold()
        return [keyword for keyword in self.keywords if keyword.casefold() in lowered]

    def _score(self, tweet: Tweet) -> float:
        engagement = tweet.like_count + (tweet.retweet_count * 3) + tweet.reply_count
        return (len(self._hits(tweet)) * 100.0) + math.log1p(max(0, engagement))

    def summarize(self, tweets: Sequence[Tweet]) -> str:
        if not tweets:
            return ""

        ranked = sorted(tweets, key=self._score, reverse=True)
        selected = ranked[: self.max_items]
        topic_counts = Counter(hit for tweet in tweets for hit in self._hits(tweet))
        account_count = len({tweet.username.casefold() for tweet in tweets})

        lines = [
            self.title,
            datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
            f"{len(tweets)} new tweets from {account_count} accounts",
        ]
        if topic_counts:
            topics = ", ".join(f"{topic} ({count})" for topic, count in topic_counts.most_common(5))
            lines.append(f"Topics: {topics}")
        lines.append("")

        for tweet in selected:
            lines.append(f"• @{tweet.username}: {_compact(tweet.text, self.max_chars_per_item)}")
            lines.append(
                f"  ♥ {tweet.like_count}  ↻ {tweet.retweet_count}  💬 {tweet.reply_count} · {tweet.url}"
            )
        remaining = len(tweets) - len(selected)
        if remaining > 0:
            lines.extend(["", f"… and {remaining} more new tweets"])
        return "\n".join(lines)

