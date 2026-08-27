from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from chart import Candle


@dataclass(frozen=True)
class Rates:
    per_sec: int
    per_min: int
    per_5min: int
    per_hour: int


RATE_ROWS = (
    ("per_sec", "/秒"),
    ("per_min", "/分"),
    ("per_5min", "/5分"),
    ("per_hour", "/时"),
)

CHART_TABS = (
    ("5分", 300.0, 1.0, "5分钟前", "/秒", 1.0, "秒均收益"),
    ("1小时", 3600.0, 60.0, "1小时前", "/分", 60.0, "分均收益"),
)


class RateTracker:
    LEVEL_CONFIRM_SECONDS = 10.0
    IDLE_CLEAR_SECONDS = 60.0

    def __init__(self, history_path: Path | None = None) -> None:
        self.history_path = Path(history_path) if history_path else None
        self._last_exp: int | None = None
        self._started_at: float | None = None
        self._first_gain_at: float | None = None
        self._last_gain_at: float | None = None
        self._last_gain: int = 0
        self._gains: deque[tuple[float, int]] = deque()
        self._pre_level_exp: int | None = None
        self._level_suspect_at: float | None = None
        if self.history_path is not None:
            self._load_history()

    @property
    def last_exp(self) -> int | None:
        return self._last_exp

    def tick(self, exp: int | None, now: float) -> Rates:
        self._record(exp, now)
        return self.hourly_rates(now)

    def hourly_rates(self, now: float) -> Rates:
        if self._first_gain_at is None:
            return Rates(0, 0, 0, 0)
        gained = self.total_gained()
        if gained <= 0:
            return Rates(0, 0, 0, 0)
        elapsed = max(now - self._first_gain_at, 1.0)
        return Rates(
            per_sec=int(round(gained / elapsed)),
            per_min=int(round(gained * 60.0 / elapsed)),
            per_5min=int(round(gained * 300.0 / elapsed)),
            per_hour=int(round(gained * 3600.0 / elapsed)),
        )

    def elapsed_since_first_gain(self, now: float) -> float | None:
        if self._first_gain_at is None:
            return None
        return max(now - self._first_gain_at, 0.0)

    def compute(self, now: float) -> Rates:
        return self.hourly_rates(now)

    def forecast(self, now: float) -> Rates:
        return self.hourly_rates(now)

    def total_gained(self) -> int:
        return sum(delta for _ts, delta in self._gains)

    def clear(self) -> None:
        self._last_exp = None
        self._started_at = None
        self._first_gain_at = None
        self._last_gain_at = None
        self._last_gain = 0
        self._gains.clear()
        self._pre_level_exp = None
        self._level_suspect_at = None
        if self.history_path is None:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text("", encoding="utf-8")

    def clear_if_idle(self, now: float, idle: float | None = None) -> bool:
        limit = self.IDLE_CLEAR_SECONDS if idle is None else idle
        if self._last_gain_at is None:
            return False
        if now - self._last_gain_at < limit:
            return False
        self.clear()
        return True

    def _record(self, exp: int | None, now: float, persist: bool = True) -> None:
        if exp is None:
            return
        if self._started_at is None:
            self._started_at = now
        if self._last_exp is None:
            self._last_exp = exp
            if persist:
                self._append_history(now, exp, 0)
            return
        if exp < self._last_exp:
            self._handle_drop(exp, now, persist)
            return
        if self._pre_level_exp is not None:
            if self._is_ocr_recovery(self._pre_level_exp, exp):
                self._last_exp = self._pre_level_exp
            self._pre_level_exp = None
            self._level_suspect_at = None
        if exp == self._last_exp:
            return
        if self._is_truncated_expansion(self._last_exp, exp):
            self._last_exp = exp
            if persist:
                self._append_history(now, exp, 0)
            return
        if not self._plausible_gain(self._last_exp, exp):
            return
        delta = exp - self._last_exp
        self._gains.append((now, delta))
        if self._first_gain_at is None:
            self._first_gain_at = now
        self._last_gain = delta
        self._last_gain_at = now
        self._last_exp = exp
        if persist:
            self._append_history(now, exp, delta)

    @staticmethod
    def _is_level_up(previous: int, new: int) -> bool:
        if new >= previous:
            return False
        return new <= previous * 0.05

    def _handle_drop(self, exp: int, now: float, persist: bool) -> None:
        if self._is_inflated_baseline(self._last_exp, exp):
            self._last_exp = exp
            if persist:
                self._append_history(now, exp, 0)
            return
        if not self._is_level_up(self._last_exp, exp):
            return
        if self._pre_level_exp is None:
            self._pre_level_exp = self._last_exp
            self._level_suspect_at = now
            return
        if (
            self._level_suspect_at is not None
            and now - self._level_suspect_at >= self.LEVEL_CONFIRM_SECONDS
        ):
            self._last_exp = exp
            self._pre_level_exp = None
            self._level_suspect_at = None
            if persist:
                self._append_history(now, exp, 0)

    @staticmethod
    def _is_ocr_recovery(previous: int, new: int) -> bool:
        if previous <= 0:
            return False
        return abs(new - previous) <= previous * 0.1

    @staticmethod
    def _is_inflated_baseline(baseline: int, reading: int) -> bool:
        if reading >= baseline:
            return False
        base_s = str(baseline)
        for trim in (1,):
            if len(base_s) <= trim:
                continue
            trimmed_s = base_s[:-trim]
            trimmed = int(trimmed_s)
            if trimmed <= 0 or reading < trimmed:
                continue
            suffix = base_s[len(trimmed_s) :]
            if len(suffix) != trim:
                continue
            inflated_cap = trimmed * (10 ** len(suffix)) + (10 ** len(suffix) - 1)
            if baseline > inflated_cap:
                continue
            if reading < trimmed * 1.01:
                continue
            if reading - trimmed <= 100:
                continue
            if reading - trimmed <= max(int(trimmed * 0.15), 5000):
                return True
        return False

    @staticmethod
    def _is_truncated_expansion(previous: int, new: int) -> bool:
        prev_s, new_s = str(previous), str(new)
        extra = len(new_s) - len(prev_s)
        if extra <= 0 or extra > 2:
            return False
        if len(prev_s) >= 4 and new_s.startswith(prev_s):
            suffix = new_s[len(prev_s) :]
            if suffix and all(ch == "0" for ch in suffix):
                return True
            return False
        scaled = previous * (10 ** extra)
        tolerance = int(scaled * 0.08)
        return tolerance > 0 and abs(new - scaled) <= tolerance

    @staticmethod
    def _plausible_gain(previous: int, new: int) -> bool:
        delta = new - previous
        if delta <= 0:
            return False
        if previous >= 1000 and delta > previous:
            return False
        return True

    def candle_series(
        self,
        now: float,
        span: float,
        candles: int = 60,
        parts: int = 4,
    ) -> list[Candle]:
        self._prune(now)
        step = span / candles
        part_step = step / parts
        previous_close = 0
        series: list[Candle] = []
        for index in range(candles):
            start = now - span + index * step
            end = start + step
            close = self._sum_between(start, end)
            part_sums = [
                self._sum_between(start + part * part_step, start + (part + 1) * part_step)
                for part in range(parts)
            ]
            high = max(previous_close, close, *part_sums)
            low = min(previous_close, close, *part_sums)
            series.append(Candle(previous_close, high, low, close))
            previous_close = close
        return series

    def rolling_minute_series(
        self,
        now: float,
        span: float = 300.0,
        step: float = 1.0,
    ) -> list[int]:
        return self._sample_series(now, span, step, window=60.0)

    def second_gain_series(
        self,
        now: float,
        span: float = 300.0,
        step: float = 1.0,
    ) -> list[int]:
        return self._sample_series(now, span, step, window=step)

    def second_increment_series(
        self,
        now: float,
        span: float = 300.0,
        step: float = 1.0,
    ) -> list[int]:
        running = 0
        totals: list[int] = []
        for gain in self.second_gain_series(now, span, step):
            running += gain
            totals.append(running)
        return totals

    def chart_rate_series(
        self,
        now: float,
        span: float,
        step: float,
        target: float,
    ) -> list[int]:
        return self._since_first_gain_series(now, span, step, target=target)

    def cumulative_series(
        self,
        now: float,
        span: float,
        step: float,
    ) -> list[int]:
        return self._since_first_gain_series(now, span, step, target=None)

    def chart_axis_start_label(self, now: float, span: float, default: str) -> str:
        if self._first_gain_at is None or self._first_gain_at > now - span:
            return "开始" if self._first_gain_at is not None else default
        return default

    def _since_first_gain_series(
        self,
        now: float,
        span: float,
        step: float,
        target: float | None,
    ) -> list[int]:
        self._prune(now)
        sample_times = self._sample_times(now, span, step)
        if self._first_gain_at is None:
            return [0] * len(sample_times)

        running = 0
        gain_idx = 0
        gains = list(self._gains)
        values: list[int] = []
        for sample in sample_times:
            while gain_idx < len(gains) and gains[gain_idx][0] <= sample:
                ts, delta = gains[gain_idx]
                if ts >= self._first_gain_at:
                    running += delta
                gain_idx += 1
            if target is None:
                values.append(running)
                continue
            if running <= 0 or sample <= self._first_gain_at:
                values.append(0)
                continue
            elapsed = max(sample - self._first_gain_at, 1.0)
            values.append(int(round(running * target / elapsed)))
        return values

    def _sample_times(self, now: float, span: float, step: float) -> list[float]:
        start = now - span
        if self._first_gain_at is not None:
            start = max(start, self._first_gain_at)
        sample = start
        times: list[float] = []
        while sample <= now + 1e-9:
            times.append(sample)
            sample += step
        if not times:
            times.append(now)
        return times

    def _sample_series(
        self,
        now: float,
        span: float,
        step: float,
        window: float,
    ) -> list[int]:
        self._prune(now)
        values: list[int] = []
        sample = now - span
        while sample <= now + 1e-9:
            values.append(self._sum_between(sample - window, sample))
            sample += step
        return values

    def _sum_since(self, cutoff: float) -> int:
        return sum(delta for ts, delta in self._gains if ts > cutoff)

    def _sum_between(self, start: float, end: float) -> int:
        return sum(delta for ts, delta in self._gains if start < ts <= end)

    def _prune(self, now: float) -> None:
        cutoff = now - 86400
        while self._gains and self._gains[0][0] < cutoff:
            self._gains.popleft()

    def _append_history(self, now: float, exp: int, delta: int) -> None:
        if self.history_path is None:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"t": now, "exp": exp, "d": delta}
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def _load_history(self) -> None:
        if self.history_path is None or not self.history_path.exists():
            return
        try:
            lines = self.history_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = float(item["t"])
            exp = int(item["exp"])
            self._record(exp, ts, persist=False)
        if self._gains:
            self._first_gain_at = self._gains[0][0]
            self._prune(self._gains[-1][0])
