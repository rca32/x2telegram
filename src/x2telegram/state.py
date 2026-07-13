from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable


class RunLock:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._stream = None

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self._stream.seek(0, os.SEEK_END)
                if self._stream.tell() == 0:
                    self._stream.write(b"\0")
                    self._stream.flush()
                self._stream.seek(0)
                msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._stream.close()
            self._stream = None
            raise RuntimeError("another x2telegram run is already active") from exc
        return self

    def __exit__(self, *args: object) -> None:
        if self._stream is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._stream.seek(0)
                msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._stream.close()
            self._stream = None


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
