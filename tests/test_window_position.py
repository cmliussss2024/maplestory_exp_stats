import json
import tempfile
import unittest
from pathlib import Path

from window_position import load_window_position, save_window_position


class WindowPositionTests(unittest.TestCase):
    def test_round_trips_x_and_y(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "window.json"
            save_window_position(path, 412, 88)
            self.assertEqual(load_window_position(path), (412, 88))

    def test_missing_file_returns_none(self):
        self.assertIsNone(load_window_position(Path("no-such-window.json")))
