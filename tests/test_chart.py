import unittest

from chart import Candle, candles_to_geometry, values_to_polyline


class ValuesToPolylineTests(unittest.TestCase):
    def test_empty_values_return_no_points(self):
        self.assertEqual(values_to_polyline([], 100, 80), [])

    def test_peak_sits_at_the_top_and_zero_at_the_bottom(self):
        points = values_to_polyline([0, 50, 100], width=100, height=100, padding=0)
        self.assertEqual(points[0], (0, 100))
        self.assertEqual(points[1], (50, 50))
        self.assertEqual(points[2], (100, 0))


class CandlesToGeometryTests(unittest.TestCase):
    def test_empty_candles_return_no_geometry(self):
        self.assertEqual(candles_to_geometry([], 100, 80), [])

    def test_higher_close_is_bullish_and_sits_above_lower_open(self):
        geom = candles_to_geometry(
            [Candle(0, 100, 0, 100)],
            width=100,
            height=100,
            padding=0,
        )
        self.assertEqual(len(geom), 1)
        self.assertTrue(geom[0].bullish)
        self.assertEqual(geom[0].body_top, 0)
        self.assertEqual(geom[0].body_bottom, 100)
        self.assertEqual(geom[0].wick_top, 0)
        self.assertEqual(geom[0].wick_bottom, 100)


class ValuesToPolylineTests(unittest.TestCase):
    def test_empty_values_return_no_points(self):
        self.assertEqual(values_to_polyline([], 100, 80), [])

    def test_peak_sits_at_the_top_and_zero_at_the_bottom(self):
        points = values_to_polyline([0, 50, 100], width=100, height=100, padding=0)
        self.assertEqual(points[0], (0, 100))
        self.assertEqual(points[1], (50, 50))
        self.assertEqual(points[2], (100, 0))
