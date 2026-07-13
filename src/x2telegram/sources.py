from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Protocol

from .models import Tweet


class TimelineSource(Protocol):
    def fetch(self) -> list[Tweet]: ...


def _parse_tweets(payload: object) -> list[Tweet]:
    if isinstance(payload, dict):
        payload = payload.get("tweets", payload.get("items", []))
    if not isinstance(payload, list):
        raise ValueError("timeline JSON must be an array or contain a tweets/items array")

    tweets: list[Tweet] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            tweets.append(Tweet.from_bird(item))
        except ValueError:
            continue
    return tweets


class BirdTimelineSource:
    def __init__(self, *, count: int, timeline: str = "following", executable: str = "bird") -> None:
        self.count = count
        self.timeline = timeline
        self.executable = executable

    @property
    def command(self) -> list[str]:
        command = [self.executable, "home"]
        if self.timeline == "following":
            command.append("--following")
        command.extend(["-n", str(self.count), "--json"])
        return command

    def fetch(self) -> list[Tweet]:
        try:
            result = subprocess.run(
                self.command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"bird CLI was not found: {self.executable}") from exc
        if result.returncode != 0:
            detail = result.stderr.strip().splitlines()
            message = detail[-1] if detail else "unknown error"
            raise RuntimeError(f"bird timeline read failed: {message}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("bird returned invalid JSON") from exc
        return _parse_tweets(payload)


class JsonFileTimelineSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def fetch(self) -> list[Tweet]:
        with self.path.open("r", encoding="utf-8-sig") as stream:
            return _parse_tweets(json.load(stream))

