from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2telegram.state import RunLock


class RunLockTests(unittest.TestCase):
    def test_second_process_style_lock_is_rejected_and_release_allows_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"
            with RunLock(lock_path):
                with self.assertRaisesRegex(RuntimeError, "already active"):
                    with RunLock(lock_path):
                        pass
            with RunLock(lock_path):
                self.assertTrue(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
