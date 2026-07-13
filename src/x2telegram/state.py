from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable


class SeenTweetStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._seen: set[str] = set()

    def load(self) -> set[str]:
        if not self.path.exists():
            self._seen = set()
            return set()
        payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
        values = payload.get("seenTweetIds", []) if isinstance(payload, dict) else []
        self._seen = {str(value) for value in values if value}
        return set(self._seen)

    def add(self, tweet_ids: Iterable[str]) -> None:
        self._seen.update(str(tweet_id) for tweet_id in tweet_ids if tweet_id)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updatedAt": datetime.now().astimezone().isoformat(),
            "seenTweetIds": sorted(self._seen),
        }
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

