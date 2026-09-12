import unittest
from pathlib import Path

import cv2
import numpy as np

from vision import (
    BOTTOM_BAND_FRACTION,
    find_label,
    label_rect_to_ocr_rect,
    scales_for_dpi,
    search_exp_label,
    to_virtual_rect,
)


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
        self.assertAlmostEqual(x, 80 + 2, delta=2)
        self.assertAlmostEqual(y, 50 + 4, delta=2)

    def test_ocr_reads_integer_from_bar_image(self):
        from vision import read_exp_from_bgr

        bar = cv2.imread(str(ASSETS / "exp_bar.png"))
        self.assertEqual(read_exp_from_bgr(bar), 139391)

    def test_ocr_reads_integer_from_live_style_crop(self):
        from vision import read_exp_from_bgr

        crop = cv2.imread(str(ASSETS / "exp_ocr.png"))
        self.assertIsNotNone(crop)
        self.assertEqual(read_exp_from_bgr(crop), 139391)

    def test_ocr_rect_hugs_exp_slot(self):
        x, y, width, height = label_rect_to_ocr_rect((8, 8, 24, 13), 400, 200)
        self.assertEqual((x, y, width, height), (7, 5, 172, 37))

    def test_locked_crop_includes_full_yellow_green_slot(self):
        from vision import crop_bgr

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
        self.assertLessEqual(ox + rw, 80 + w)
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

    def test_scales_for_dpi_shortlists(self):
        self.assertIn(1.0, scales_for_dpi(1.0))
        self.assertNotIn(3.0, scales_for_dpi(1.0))
        self.assertIn(1.5, scales_for_dpi(1.5))
        self.assertNotIn(3.0, scales_for_dpi(1.5))


class SearchFunnelTests(unittest.TestCase):
    def setUp(self):
        bar = cv2.imread(str(ASSETS / "exp_bar.png"))
        self.assertIsNotNone(bar)
        self.bar = bar
        self.bh, self.bw = bar.shape[:2]
        self.monitors = [
            {"index": 1, "left": 0, "top": 0, "width": 800, "height": 600},
        ]

    def _paste(self, canvas: np.ndarray, x: int, y: int) -> None:
        canvas[y : y + self.bh, x : x + self.bw] = self.bar

    def test_band_hit_skips_upper_remainder(self):
        grabs: list[tuple[int, int, int, int]] = []
        height = 600
        band_h = int(round(height * BOTTOM_BAND_FRACTION))
        band_top = height - band_h
        band = np.zeros((band_h, 800, 3), dtype=np.uint8)
        self._paste(band, 100, max(0, band_h - self.bh - 5))

        def grab(left, top, width, height):
            grabs.append((left, top, width, height))
            if top == band_top and height == band_h:
                return band
            raise AssertionError("upper remainder should not be grabbed on band hit")

        hit, mon = search_exp_label(
            grab_fn=grab,
            monitors_fn=lambda: self.monitors,
            dpi_fn=lambda _x, _y: 1.0,
        )
        self.assertIsNotNone(hit)
        self.assertEqual(mon, 1)
        self.assertEqual(len(grabs), 1)
        self.assertEqual(grabs[0][1], band_top)

    def test_upper_only_hit_after_band_miss(self):
        grabs: list[tuple[int, int, int, int]] = []
        height = 600
        band_h = int(round(height * BOTTOM_BAND_FRACTION))
        upper_h = height - band_h
        upper = np.zeros((upper_h, 800, 3), dtype=np.uint8)
        self._paste(upper, 50, 20)
        empty_band = np.zeros((band_h, 800, 3), dtype=np.uint8)

        def grab(left, top, width, height):
            grabs.append((left, top, width, height))
            if top == 0 and height == upper_h:
                return upper
            return empty_band

        hit, mon = search_exp_label(
            grab_fn=grab,
            monitors_fn=lambda: self.monitors,
            dpi_fn=lambda _x, _y: 1.0,
        )
        self.assertIsNotNone(hit)
        self.assertEqual(mon, 1)
        self.assertEqual(len(grabs), 2)
        self.assertEqual(grabs[0][1], height - band_h)
        self.assertEqual(grabs[1][1], 0)

    def test_neighborhood_preferred_over_monitor_scan(self):
        grabs: list[tuple[int, int, int, int]] = []
        # last_rect (100,100,121,34) + pad 300 → neighborhood region (0,0,521,434)
        pad_canvas = np.zeros((434, 521, 3), dtype=np.uint8)
        self._paste(pad_canvas, 100, 100)

        def grab(left, top, width, height):
            grabs.append((left, top, width, height))
            if (left, top, width, height) == (0, 0, 521, 434):
                return pad_canvas
            raise AssertionError("monitor bands should not run after neighborhood hit")

        hit, mon = search_exp_label(
            last_rect=(100, 100, 121, 34),
            last_monitor_index=1,
            grab_fn=grab,
            monitors_fn=lambda: self.monitors,
            dpi_fn=lambda _x, _y: 1.0,
        )
        self.assertIsNotNone(hit)
        self.assertEqual(mon, 1)
        self.assertEqual(len(grabs), 1)


if __name__ == "__main__":
    unittest.main()
