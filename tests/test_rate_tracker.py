import json
import tempfile
import unittest
from pathlib import Path

from rate_tracker import RateTracker


class RealtimeRateTrackerTests(unittest.TestCase):
    def test_first_reading_establishes_baseline_with_zero_rates(self):
        tracker = RateTracker()
        rates = tracker.tick(256163, now=0.0)
        self.assertEqual(rates.per_second, 0)
        self.assertEqual(rates.per_minute, 0)
        self.assertEqual(rates.per_hour, 0)

    def test_positive_gain_fills_all_three_rates(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        rates = tracker.tick(1500, now=1.0)
        self.assertEqual(rates.per_second, 500)
        self.assertEqual(rates.per_minute, 500)
        self.assertEqual(rates.per_hour, 30000)

    def test_ocr_miss_does_not_change_rates(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1500, now=1.0)
        rates = tracker.tick(None, now=2.0)
        self.assertEqual(rates.per_second, 500)
        self.assertEqual(rates.per_minute, 500)

    def test_level_up_drop_is_not_negative_gain(self):
        tracker = RateTracker()
        tracker.tick(90000, now=0.0)
        tracker.tick(95000, now=1.0)
        rates = tracker.tick(120, now=2.0)
        self.assertEqual(rates.per_second, 5000)
        self.assertEqual(rates.per_minute, 5000)

    def test_per_second_zeros_after_15s_idle(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        rates = tracker.tick(1100, now=16.1)
        self.assertEqual(rates.per_second, 0)
        self.assertEqual(rates.per_minute, 100)

    def test_per_minute_zeros_after_60s_idle(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        rates = tracker.tick(1100, now=61.1)
        self.assertEqual(rates.per_minute, 0)
        self.assertEqual(rates.per_hour, 6000)

    def test_per_hour_zeros_after_5_minutes_idle(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        rates = tracker.tick(1100, now=301.1)
        self.assertEqual(rates.per_second, 0)
        self.assertEqual(rates.per_minute, 0)
        self.assertEqual(rates.per_hour, 0)

    def test_ocr_jump_is_not_treated_as_one_second_gain(self):
        tracker = RateTracker()
        tracker.tick(8486, now=0.0)
        rates = tracker.tick(1_359_000, now=1.0)
        self.assertEqual(rates.per_second, 0)
        self.assertEqual(rates.per_minute, 0)
        self.assertEqual(rates.per_hour, 0)
        self.assertEqual(tracker.last_exp, 8486)

    def test_ocr_truncated_drop_is_ignored_so_later_gains_count(self):
        tracker = RateTracker(mode="average")
        tracker.tick(25852, now=0.0)
        tracker.tick(2586, now=1.0)
        rates = tracker.tick(25863, now=2.0)
        self.assertEqual(tracker.last_exp, 25863)
        self.assertGreater(rates.per_second, 0)
        self.assertGreater(rates.per_hour, 4)


class AverageRateTrackerTests(unittest.TestCase):
    def test_short_session_hourly_is_not_diluted_by_24_hours(self):
        tracker = RateTracker(mode="average")
        tracker.tick(25000, now=0.0)
        rates = tracker.tick(25100, now=10.0)
        self.assertEqual(rates.per_second, 10)
        self.assertEqual(rates.per_minute, 600)
        self.assertEqual(rates.per_hour, 36000)

    def test_average_per_second_uses_last_60_seconds(self):
        tracker = RateTracker(mode="average")
        tracker.tick(0, now=0.0)
        for second in range(1, 61):
            tracker.tick(second * 100, now=float(second))
        rates = tracker.compute(60.0, "average")
        self.assertEqual(rates.per_second, 100)

    def test_toggle_recomputes_without_new_reading(self):
        tracker = RateTracker(mode="realtime")
        tracker.tick(1000, now=0.0)
        tracker.tick(1600, now=1.0)
        realtime = tracker.compute(1.0, "realtime")
        average = tracker.compute(1.0, "average")
        self.assertEqual(realtime.per_second, 600)
        self.assertEqual(realtime.per_hour, 36000)
        self.assertEqual(average.per_second, 600)
        self.assertEqual(average.per_hour, 2_160_000)


class HistoryPersistTests(unittest.TestCase):
    def test_reloads_gains_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            first = RateTracker(history_path=path)
            first.tick(1000, now=1_700_000_000.0)
            first.tick(1100, now=1_700_000_001.0)
            second = RateTracker(history_path=path)
            rates = second.compute(1_700_000_001.0, "average")
            self.assertEqual(second.last_exp, 1100)
            self.assertEqual(rates.per_second, 100)
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 2)
            last = json.loads(lines[-1])
            self.assertEqual(last["exp"], 1100)
            self.assertEqual(last["d"], 100)
