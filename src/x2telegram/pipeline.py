from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Tweet
from .senders import Sender
from .sources import TimelineSource
from .state import SeenTweetStore
from .summarizers import Summarizer


@dataclass(frozen=True, slots=True)
class RunResult:
    fetched_count: int
    matched_count: int
    new_count: int
    sent_chunks: int
    digest: str


class Pipeline:
    def __init__(
        self,
        *,
        source: TimelineSource,
        summarizer: Summarizer,
        state: SeenTweetStore,
        sender: Sender | None = None,
        accounts: Iterable[str] = (),
    ) -> None:
        self.source = source
        self.summarizer = summarizer
        self.state = state
        self.sender = sender
        self.accounts = {account.casefold().lstrip("@") for account in accounts if account.strip()}

    def run(self, *, dry_run: bool = False) -> RunResult:
        fetched = self.source.fetch()
        matched = [
            tweet for tweet in fetched if not self.accounts or tweet.username.casefold() in self.accounts
        ]
        seen = self.state.load()
        unique: dict[str, Tweet] = {}
        for tweet in matched:
            if tweet.id not in seen:
                unique.setdefault(tweet.id, tweet)
        new_tweets = list(unique.values())
        digest = self.summarizer.summarize(new_tweets)

        sent_chunks = 0
        if new_tweets and not dry_run:
            if self.sender is None:
                raise ValueError("a sender is required unless --dry-run is used")
            sent_chunks = self.sender.send(digest)
            self.state.add(tweet.id for tweet in new_tweets)
            self.state.save()

        return RunResult(
            fetched_count=len(fetched),
            matched_count=len(matched),
            new_count=len(new_tweets),
            sent_chunks=sent_chunks,
            digest=digest,
        )

