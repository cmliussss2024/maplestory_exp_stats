import unittest
from pathlib import Path

import cv2
import numpy as np

from vision import find_label, read_exp_from_bgr, to_virtual_rect


ASSETS = Path(__file__).resolve().parents[1] / "assets"


class VisionTests(unittest.TestCase):
    def test_finds_exp_label_inside_bar_image(self):
        bar = cv2.imread(str(ASSETS / "exp_bar.png"))
        self.assertIsNotNone(bar)
        screen = np.zeros((200, 400, 3), dtype=np.uint8)
        screen[50:91, 80:215] = bar
        rect, score = find_label(screen)
        self.assertIsNotNone(rect)
        self.assertGreater(score, 0.8)
        x, y, _w, _h = rect
        self.assertAlmostEqual(x, 80 + 8, delta=2)
        self.assertAlmostEqual(y, 50 + 8, delta=2)

    def test_ocr_reads_integer_from_bar_image(self):
        bar = cv2.imread(str(ASSETS / "exp_bar.png"))
        self.assertEqual(read_exp_from_bgr(bar), 256163)

    def test_converts_screenshot_rect_to_virtual_screen(self):
        self.assertEqual(
            to_virtual_rect((3694, 1221, 150, 22), (-2560, 0)),
            (1134, 1221, 150, 22),
        )
