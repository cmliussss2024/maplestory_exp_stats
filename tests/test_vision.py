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
        h, w = bar.shape[:2]
        screen = np.zeros((200, 400, 3), dtype=np.uint8)
        screen[50 : 50 + h, 80 : 80 + w] = bar
        rect, score = find_label(screen)
        self.assertIsNotNone(rect)
        self.assertGreater(score, 0.8)
        x, y, _w, _h = rect
        self.assertAlmostEqual(x, 80 + 7, delta=2)
        self.assertAlmostEqual(y, 50 + 5, delta=2)

    def test_ocr_reads_integer_from_bar_image(self):
        bar = cv2.imread(str(ASSETS / "exp_bar.png"))
        self.assertEqual(read_exp_from_bgr(bar), 176792)

    def test_ocr_reads_integer_from_live_style_crop(self):
        crop = cv2.imread(str(ASSETS / "exp_ocr.png"))
        self.assertIsNotNone(crop)
        self.assertEqual(read_exp_from_bgr(crop), 176155)

    def test_ocr_rect_hugs_exp_slot(self):
        from vision import label_rect_to_ocr_rect

        x, y, width, height = label_rect_to_ocr_rect((8, 8, 24, 13), 400, 200)
        self.assertEqual((x, y, width, height), (7, 6, 121, 34))

    def test_locked_crop_includes_full_yellow_green_slot(self):
        from vision import crop_bgr, label_rect_to_ocr_rect

        bar = cv2.imread(str(ASSETS / "exp_bar.png"))
        self.assertIsNotNone(bar)
        h, w = bar.shape[:2]
        screen = np.zeros((200, 400, 3), dtype=np.uint8)
        screen[50 : 50 + h, 80 : 80 + w] = bar
        label_rect, _score = find_label(screen)
        self.assertIsNotNone(label_rect)
        rect = label_rect_to_ocr_rect(label_rect, 400, 200)
        ox, oy, rw, rh = rect
        self.assertGreater(ox, 80)
        self.assertGreater(oy, 50)
        self.assertLess(ox + rw, 80 + w)
        self.assertLess(oy + rh, 50 + h)
        crop = crop_bgr(screen, rect)
        _b, g, r = cv2.split(crop)
        yg = (g > 140) & (g > r) & (g > (_b.astype(np.int16) + 20))
        ys, xs = np.where(yg)
        self.assertGreater(int(yg.sum()), 400)
        self.assertGreaterEqual(int(xs.max() - xs.min()), 50)
        self.assertGreaterEqual(int(ys.max() - ys.min()), 8)

    def test_converts_screenshot_rect_to_virtual_screen(self):
        self.assertEqual(
            to_virtual_rect((3694, 1221, 150, 22), (-2560, 0)),
            (1134, 1221, 150, 22),
        )
