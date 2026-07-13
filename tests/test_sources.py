from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from x2telegram.sources import BirdTimelineSource


class BirdTimelineSourceTests(unittest.TestCase):
    def test_windows_command_shim_is_resolved_before_run(self) -> None:
        resolved = r"C:\tools\bird.CMD"
        completed = subprocess.CompletedProcess([resolved], 0, "[]", "")
        source = BirdTimelineSource(count=7)

        with patch("x2telegram.sources.shutil.which", return_value=resolved):
            with patch("x2telegram.sources.subprocess.run", return_value=completed) as run:
                tweets = source.fetch()

        self.assertEqual(tweets, [])
        command = run.call_args.args[0]
        self.assertEqual(command[0], resolved)
        self.assertEqual(command[-3:], ["-n", "7", "--json"])


if __name__ == "__main__":
    unittest.main()

