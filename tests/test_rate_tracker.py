import json
import tempfile
import unittest
from pathlib import Path

from chart import Candle
from rate_tracker import ExpPoint, RateTracker, Rates, sanitize_exp_series


class HourlyRateTests(unittest.TestCase):
    def test_baseline_has_zero_rates(self):
        rates = RateTracker().tick(256163, now=0.0)
        self.assertEqual(rates, Rates(0, 0, 0, 0))

    def test_first_gain_scales_to_hourly_rates(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        rates = tracker.tick(1500, now=1.0)
        self.assertEqual(rates.per_sec, 500)
        self.assertEqual(rates.per_min, 30000)
        self.assertEqual(rates.per_5min, 150000)
        self.assertEqual(rates.per_hour, 1_800_000)

    def test_ocr_miss_does_not_change_rates(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1500, now=1.0)
        rates = tracker.tick(None, now=2.0)
        self.assertEqual(rates.per_min, 30000)

    def test_level_up_drop_is_not_negative_gain(self):
        tracker = RateTracker()
        tracker.tick(90000, now=0.0)
        tracker.tick(95000, now=1.0)
        rates = tracker.tick(120, now=12.0)
        self.assertEqual(tracker.total_gained(), 5000)
        self.assertEqual(rates.per_hour, int(round(5000 * 3600 / 11)))

    def test_rates_use_all_gains_since_first_gain(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        rates = tracker.hourly_rates(61.0)
        self.assertEqual(rates.per_min, 100)
        self.assertEqual(rates.per_hour, 6000)

    def test_ocr_jump_is_not_treated_as_gain(self):
        tracker = RateTracker()
        tracker.tick(8486, now=0.0)
        rates = tracker.tick(1_359_000, now=1.0)
        self.assertEqual(rates, Rates(0, 0, 0, 0))
        self.assertEqual(tracker.last_exp, 8486)

    def test_ocr_truncated_drop_is_ignored_so_later_gains_count(self):
        tracker = RateTracker()
        tracker.tick(25852, now=0.0)
        tracker.tick(2586, now=1.0)
        rates = tracker.tick(25863, now=2.0)
        self.assertEqual(tracker.last_exp, 25863)
        self.assertGreater(rates.per_min, 0)

    def test_steady_gains_average_over_elapsed_time(self):
        tracker = RateTracker()
        tracker.tick(0, now=0.0)
        for second in range(1, 61):
            tracker.tick(second * 100, now=float(second))
        rates = tracker.hourly_rates(60.0)
        self.assertEqual(tracker.total_gained(), 6000)
        self.assertEqual(rates.per_min, int(round(6000 * 60 / 59)))

    def test_elapsed_since_first_gain(self):
        tracker = RateTracker()
        tracker.tick(1000, now=10.0)
        tracker.tick(1100, now=25.0)
        self.assertEqual(tracker.elapsed_since_first_gain(40.0), 15.0)


class IdleClearTests(unittest.TestCase):
    def test_does_not_clear_before_one_minute_without_gain(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        self.assertFalse(tracker.clear_if_idle(now=60.0))
        self.assertEqual(tracker.hourly_rates(60.0).per_min, int(round(100 * 60 / 59)))

    def test_clears_after_one_minute_without_gain(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        self.assertTrue(tracker.clear_if_idle(now=61.1))
        self.assertIsNone(tracker.last_exp)
        self.assertEqual(tracker.hourly_rates(61.1), Rates(0, 0, 0, 0))


class HistoryPersistTests(unittest.TestCase):
    def test_reloads_gains_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            first = RateTracker(history_path=path)
            first.tick(1000, now=1_700_000_000.0)
            first.tick(1100, now=1_700_000_001.0)
            second = RateTracker(history_path=path)
            rates = second.hourly_rates(1_700_000_001.0)
            self.assertEqual(second.last_exp, 1100)
            self.assertEqual(rates.per_min, 6000)
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 2)
            last = json.loads(lines[-1])
            self.assertEqual(last["exp"], 1100)
            self.assertNotIn("d", last)
            self.assertEqual(set(last), {"t", "exp"})
            t_text = lines[-1].split('"t": ', 1)[1].split(",", 1)[0]
            self.assertRegex(t_text, r"^\d+\.\d{6}$")

    def test_clear_resets_memory_and_truncates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            tracker = RateTracker(history_path=path)
            tracker.tick(1000, now=1_700_000_000.0)
            tracker.tick(1100, now=1_700_000_001.0)
            tracker.clear()
            rates = tracker.hourly_rates(1_700_000_001.0)
            self.assertIsNone(tracker.last_exp)
            self.assertEqual(rates, Rates(0, 0, 0, 0))
            self.assertEqual(path.read_text(encoding="utf-8"), "")
            reloaded = RateTracker(history_path=path)
            self.assertIsNone(reloaded.last_exp)

    def test_clear_without_history_path_resets_memory(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        tracker.clear()
        self.assertIsNone(tracker.last_exp)
        rates = tracker.hourly_rates(1.0)
        self.assertEqual(rates, Rates(0, 0, 0, 0))

    def test_clear_then_tick_starts_fresh_baseline(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        tracker.clear()
        tracker.tick(2000, now=2.0)
        rates = tracker.tick(2100, now=3.0)
        self.assertEqual(tracker.last_exp, 2100)
        self.assertEqual(rates.per_min, 6000)

    def test_timestamp_is_serialized_with_six_decimals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            tracker = RateTracker(history_path=path)
            tracker.tick(1000, now=1787839419.03855)
            line = path.read_text(encoding="utf-8").strip()
            self.assertEqual(line, '{"t": 1787839419.038550, "exp": 1000}')

    def test_drop_is_persisted_and_skipped_on_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            first = RateTracker(history_path=path)
            first.tick(10001, now=1.0)
            first.tick(1010, now=2.0)
            first.tick(10204, now=3.0)
            text = path.read_text(encoding="utf-8")
            self.assertIn('"exp": 1010', text)
            second = RateTracker(history_path=path)
            self.assertEqual(second.last_exp, 10204)
            self.assertEqual(second.total_gained(), 203)

    def test_legacy_records_with_d_still_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            path.write_text(
                '{"t": 1787766181.7113051, "exp": 1000, "d": 0}\n'
                '{"t": 1787766182.1234567, "exp": 1100, "d": 100}\n',
                encoding="utf-8",
            )
            tracker = RateTracker(history_path=path)
            self.assertEqual(tracker.last_exp, 1100)
            self.assertEqual(tracker.total_gained(), 100)


class RollingMinuteSeriesTests(unittest.TestCase):
    def test_empty_tracker_fills_span_with_zeros(self):
        tracker = RateTracker()
        self.assertEqual(
            tracker.rolling_minute_series(now=10.0, span=2.0, step=1.0),
            [0, 0, 0],
        )

    def test_steady_gains_fill_the_trailing_minute(self):
        tracker = RateTracker()
        tracker.tick(0, now=0.0)
        for second in range(1, 121):
            tracker.tick(second * 10, now=float(second))
        series = tracker.rolling_minute_series(now=120.0, span=5.0, step=1.0)
        self.assertEqual(series, [600, 600, 600, 600, 600, 600])

    def test_gain_drops_out_after_sixty_seconds(self):
        tracker = RateTracker()
        tracker.tick(100, now=0.0)
        tracker.tick(200, now=10.0)
        series = tracker.rolling_minute_series(now=70.0, span=2.0, step=1.0)
        self.assertEqual(series, [100, 100, 0])


class ChartSeriesTests(unittest.TestCase):
    def test_empty_chart_series_are_zeros(self):
        tracker = RateTracker()
        self.assertEqual(tracker.chart_rate_series(10.0, 2.0, 1.0, 1.0), [0, 0, 0])
        self.assertEqual(tracker.cumulative_series(10.0, 2.0, 1.0), [0, 0, 0])

    def test_chart_rate_series_uses_hourly_income_since_first_gain(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        series = tracker.chart_rate_series(10.0, span=5.0, step=1.0, target=1.0)
        self.assertEqual(series[-1], 11)

    def test_cumulative_series_tracks_total_since_first_gain(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        tracker.tick(1200, now=5.0)
        series = tracker.cumulative_series(10.0, span=5.0, step=1.0)
        self.assertEqual(series[-1], 200)

    def test_chart_axis_start_label_switches_to_beginning(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=8.0)
        self.assertEqual(tracker.chart_axis_start_label(10.0, 5.0, "5分钟前"), "开始")


class SecondSeriesTests(unittest.TestCase):
    def test_empty_second_gain_series_is_zeros(self):
        tracker = RateTracker()
        self.assertEqual(
            tracker.second_gain_series(now=10.0, span=2.0, step=1.0),
            [0, 0, 0],
        )

    def test_second_gain_series_buckets_each_second(self):
        tracker = RateTracker()
        tracker.tick(0, now=0.0)
        tracker.tick(10, now=1.0)
        tracker.tick(10, now=2.0)
        tracker.tick(25, now=3.0)
        self.assertEqual(
            tracker.second_gain_series(now=3.0, span=2.0, step=1.0),
            [10, 0, 15],
        )

    def test_second_increment_series_is_running_total(self):
        tracker = RateTracker()
        tracker.tick(0, now=0.0)
        tracker.tick(10, now=1.0)
        tracker.tick(10, now=2.0)
        tracker.tick(25, now=3.0)
        self.assertEqual(
            tracker.second_increment_series(now=3.0, span=2.0, step=1.0),
            [10, 10, 25],
        )


class CandleSeriesTests(unittest.TestCase):
    def test_empty_candles_are_flat_zeros(self):
        candles = RateTracker().candle_series(now=10.0, span=2.0, candles=2, parts=2)
        self.assertEqual(candles, [Candle(0, 0, 0, 0), Candle(0, 0, 0, 0)])

    def test_close_is_gain_in_that_bucket_and_open_is_previous_close(self):
        tracker = RateTracker()
        tracker.tick(0, now=0.0)
        tracker.tick(10, now=1.0)
        tracker.tick(10, now=2.0)
        tracker.tick(30, now=3.0)
        first, second = tracker.candle_series(now=3.0, span=2.0, candles=2, parts=2)
        self.assertEqual(first.close, 0)
        self.assertEqual(second.open, first.close)
        self.assertEqual(second.close, 20)
        self.assertEqual(second.high, 20)
        self.assertEqual(second.low, 0)


class OcrRecoveryTests(unittest.TestCase):
    def test_truncated_drop_then_nearby_reading_is_not_a_huge_gain(self):
        tracker = RateTracker()
        tracker.tick(33252, now=0.0)
        tracker.tick(325, now=1.0)
        rates = tracker.tick(33402, now=2.0)
        self.assertEqual(tracker.last_exp, 33402)
        self.assertEqual(tracker.total_gained(), 150)
        self.assertEqual(rates.per_min, 9000)

    def test_truncated_drop_with_small_blip_still_recovers(self):
        tracker = RateTracker()
        tracker.tick(44356, now=0.0)
        tracker.tick(420, now=1.0)
        tracker.tick(499, now=2.0)
        rates = tracker.tick(44531, now=3.0)
        self.assertEqual(tracker.last_exp, 44531)
        self.assertEqual(tracker.total_gained(), 175)
        self.assertEqual(rates.per_min, 10500)

    def test_confirmed_level_up_keeps_the_new_baseline(self):
        tracker = RateTracker()
        tracker.tick(90000, now=0.0)
        tracker.tick(95000, now=1.0)
        tracker.tick(120, now=2.0)
        tracker.tick(200, now=3.0)
        tracker.tick(280, now=13.0)
        rates = tracker.tick(360, now=14.0)
        self.assertEqual(tracker.last_exp, 360)
        self.assertEqual(tracker.total_gained(), 5240)
        self.assertEqual(rates.per_hour, int(round(5240 * 3600 / 13)))

    def test_two_truncated_readings_do_not_confirm_a_fake_level_up(self):
        tracker = RateTracker()
        tracker.tick(55497, now=0.0)
        tracker.tick(516, now=1.0)
        tracker.tick(581, now=2.0)
        tracker.tick(590, now=3.0)
        rates = tracker.tick(55604, now=4.0)
        self.assertEqual(tracker.last_exp, 55604)
        self.assertEqual(tracker.total_gained(), 107)
        self.assertEqual(rates.per_min, 6420)

    def test_truncated_baseline_recovers_to_full_value_without_huge_gain(self):
        tracker = RateTracker()
        tracker.tick(6685, now=0.0)
        rates = tracker.tick(67106, now=1.0)
        self.assertEqual(tracker.last_exp, 67106)
        self.assertEqual(rates.per_min, 0)

    def test_suffix_digit_ocr_noise_does_not_inflate_baseline(self):
        tracker = RateTracker()
        tracker.tick(103546, now=0.0)
        rates = tracker.tick(1035461, now=1.0)
        self.assertEqual(tracker.last_exp, 103546)
        self.assertEqual(rates.per_min, 0)

    def test_recovers_from_inflated_baseline_and_counts_gains_again(self):
        tracker = RateTracker()
        tracker.tick(1035461, now=0.0)
        tracker.tick(107016, now=2.0)
        tracker.tick(107062, now=3.0)
        rates = tracker.tick(107108, now=4.0)
        self.assertEqual(tracker.last_exp, 107108)
        self.assertEqual(tracker.total_gained(), 92)
        self.assertEqual(rates.per_min, 5520)

    def test_same_order_of_magnitude_gain_is_still_counted(self):
        tracker = RateTracker()
        tracker.tick(100, now=0.0)
        rates = tracker.tick(1100, now=1.0)
        self.assertEqual(tracker.last_exp, 1100)
        self.assertEqual(rates.per_min, 60000)


class ForecastAliasTests(unittest.TestCase):
    def test_forecast_matches_hourly_rates(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=10.0)
        self.assertEqual(tracker.forecast(10.0), tracker.hourly_rates(10.0))

    def test_forecast_is_zero_when_idle(self):
        tracker = RateTracker()
        tracker.tick(1000, now=0.0)
        tracker.tick(1100, now=1.0)
        tracker.clear_if_idle(now=61.1)
        rates = tracker.forecast(61.1)
        self.assertEqual(rates, Rates(0, 0, 0, 0))


class SanitizeExpSeriesTests(unittest.TestCase):
    def test_single_ocr_valley_is_skipped(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 10001), ExpPoint(1.0, 1010), ExpPoint(2.0, 10204)],
            now=2.0,
        )
        self.assertEqual(result.last_exp, 10204)
        self.assertEqual(sum(delta for _t, delta in result.gains), 203)

    def test_repeated_ocr_valley_is_skipped(self):
        points = [ExpPoint(0.0, 10099)]
        points.extend(ExpPoint(float(i), 1010) for i in range(1, 6))
        points.append(ExpPoint(6.0, 10200))
        result = sanitize_exp_series(points, now=6.0)
        self.assertEqual(result.last_exp, 10200)
        self.assertEqual(sum(delta for _t, delta in result.gains), 101)

    def test_jittered_ocr_valley_is_skipped(self):
        result = sanitize_exp_series(
            [
                ExpPoint(0.0, 10099),
                ExpPoint(1.0, 1010),
                ExpPoint(2.0, 1015),
                ExpPoint(3.0, 1020),
                ExpPoint(4.0, 10200),
            ],
            now=4.0,
        )
        self.assertEqual(result.last_exp, 10200)
        self.assertEqual(sum(delta for _t, delta in result.gains), 101)

    def test_confirmed_level_up_accumulates_both_sides(self):
        result = sanitize_exp_series(
            [
                ExpPoint(0.0, 90000),
                ExpPoint(1.0, 95000),
                ExpPoint(2.0, 120),
                ExpPoint(3.0, 200),
                ExpPoint(13.0, 280),
                ExpPoint(14.0, 360),
            ],
            now=14.0,
        )
        self.assertEqual(result.last_exp, 360)
        self.assertEqual(sum(delta for _t, delta in result.gains), 5240)

    def test_unconfirmed_valley_keeps_previous_baseline(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 10099), ExpPoint(1.0, 1010)],
            now=6.0,
        )
        self.assertEqual(result.last_exp, 10099)
        self.assertEqual(result.gains, ())

    def test_timeout_confirms_level_up(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 10099), ExpPoint(1.0, 1010)],
            now=16.0,
        )
        self.assertEqual(result.last_exp, 1010)
        self.assertEqual(result.gains, ())

    def test_recovery_after_timeout_reclassifies_as_ocr(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 10099), ExpPoint(1.0, 1010), ExpPoint(16.0, 10200)],
            now=16.0,
        )
        self.assertEqual(result.last_exp, 10200)
        self.assertEqual(sum(delta for _t, delta in result.gains), 101)

    def test_gradual_climb_after_level_up_is_not_ocr(self):
        points = [ExpPoint(0.0, 10099), ExpPoint(1.0, 50)]
        exp = 50
        for second in range(2, 122):
            exp += 100
            points.append(ExpPoint(float(second), exp))
        result = sanitize_exp_series(points, now=121.0)
        self.assertEqual(result.last_exp, exp)
        self.assertEqual(sum(delta for _t, delta in result.gains), exp - 50)
        self.assertNotEqual(sum(delta for _t, delta in result.gains), exp - 10099)

    def test_implausible_jump_is_skipped(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 8486), ExpPoint(1.0, 1_359_000)],
            now=1.0,
        )
        self.assertEqual(result.last_exp, 8486)
        self.assertEqual(result.gains, ())

    def test_truncated_drop_recovers(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 25852), ExpPoint(1.0, 2586), ExpPoint(2.0, 25863)],
            now=2.0,
        )
        self.assertEqual(result.last_exp, 25863)
        self.assertEqual(sum(delta for _t, delta in result.gains), 11)

    def test_truncated_expansion_resets_baseline(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 6685), ExpPoint(1.0, 67106)],
            now=1.0,
        )
        self.assertEqual(result.last_exp, 67106)
        self.assertEqual(result.gains, ())

    def test_suffix_noise_is_not_a_gain(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 103546), ExpPoint(1.0, 1035461)],
            now=1.0,
        )
        self.assertEqual(result.last_exp, 103546)
        self.assertEqual(result.gains, ())

    def test_inflated_baseline_recovers(self):
        result = sanitize_exp_series(
            [
                ExpPoint(0.0, 1035461),
                ExpPoint(2.0, 107016),
                ExpPoint(3.0, 107062),
                ExpPoint(4.0, 107108),
            ],
            now=4.0,
        )
        self.assertEqual(result.last_exp, 107108)
        self.assertEqual(sum(delta for _t, delta in result.gains), 92)
