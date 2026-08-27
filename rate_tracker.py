from __future__ import annotations

import json
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from chart import Candle


@dataclass(frozen=True)
class ExpPoint:
    t: float
    exp: int


@dataclass(frozen=True)
class SanitizedExp:
    last_exp: int | None
    gains: tuple[tuple[float, int], ...]
    first_gain_at: float | None
    last_gain_at: float | None
    last_gain: int


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

LEVEL_CONFIRM_SECONDS = 10.0


def _round_t(now: float) -> float:
    return float(format(now, ".6f"))


def _plausible_gain(previous: int, new: int) -> bool:
    delta = new - previous
    if delta <= 0:
        return False
    if previous >= 1000 and delta > previous:
        return False
    return True


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


def _is_recovery_jump(a_exp: int, v_exp: int, c_exp: int) -> bool:
    if c_exp < a_exp:
        return False
    if c_exp == a_exp:
        return True
    if not _plausible_gain(a_exp, c_exp):
        return False
    if not _plausible_gain(v_exp, c_exp):
        return True
    return len(str(c_exp)) > len(str(v_exp))


def sanitize_exp_series(points: Sequence[ExpPoint], now: float) -> SanitizedExp:
    if not points:
        return SanitizedExp(None, (), None, None, 0)

    accepted: list[ExpPoint] = []
    gains: list[tuple[float, int]] = []

    def accept(point: ExpPoint, delta: int) -> None:
        accepted.append(point)
        if delta > 0:
            gains.append((point.t, delta))

    accept(points[0], 0)
    index = 1
    count = len(points)
    while index < count:
        current = points[index]
        previous = accepted[-1]
        if current.exp == previous.exp:
            index += 1
            continue
        if current.exp > previous.exp:
            if _is_truncated_expansion(previous.exp, current.exp):
                accept(current, 0)
            elif _plausible_gain(previous.exp, current.exp):
                accept(current, current.exp - previous.exp)
            index += 1
            continue
        if _is_inflated_baseline(previous.exp, current.exp):
            accept(current, 0)
            index += 1
            continue
        anchor = previous
        valley_start = index
        recovered_at: int | None = None
        cursor = index + 1
        while cursor < count:
            candidate = points[cursor]
            valley_last = points[cursor - 1]
            if _is_recovery_jump(anchor.exp, valley_last.exp, candidate.exp):
                recovered_at = cursor
                break
            cursor += 1
        if recovered_at is not None:
            recovered = points[recovered_at]
            accept(recovered, recovered.exp - anchor.exp)
            index = recovered_at + 1
            continue
        valley_first = points[valley_start]
        if now - valley_first.t >= LEVEL_CONFIRM_SECONDS:
            accept(valley_first, 0)
            index = valley_start + 1
            continue
        break

    last_exp = accepted[-1].exp
    first_gain_at = gains[0][0] if gains else None
    last_gain_at = gains[-1][0] if gains else None
    last_gain = gains[-1][1] if gains else 0
    return SanitizedExp(last_exp, tuple(gains), first_gain_at, last_gain_at, last_gain)


class RateTracker:
    LEVEL_CONFIRM_SECONDS = LEVEL_CONFIRM_SECONDS
    IDLE_CLEAR_SECONDS = 60.0

    def __init__(self, history_path: Path | None = None) -> None:
        self.history_path = Path(history_path) if history_path else None
        self._points: list[ExpPoint] = []
        self._last_exp: int | None = None
        self._started_at: float | None = None
        self._first_gain_at: float | None = None
        self._last_gain_at: float | None = None
        self._last_gain: int = 0
        self._gains: deque[tuple[float, int]] = deque()
        if self.history_path is not None:
            self._load_history()

    @property
    def last_exp(self) -> int | None:
        return self._last_exp

    def tick(self, exp: int | None, now: float) -> Rates:
        self._record(exp, now)
        return self.hourly_rates(now)

    def hourly_rates(self, now: float) -> Rates:
        self._refresh(now)
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
        self._points.clear()
        self._last_exp = None
        self._started_at = None
        self._first_gain_at = None
        self._last_gain_at = None
        self._last_gain = 0
        self._gains.clear()
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
        stamped = _round_t(now)
        if self._started_at is None:
            self._started_at = stamped
        if self._points and self._points[-1].exp == exp:
            return
        self._points.append(ExpPoint(stamped, exp))
        if persist:
            self._append_history(stamped, exp)

    def _refresh(self, now: float) -> None:
        result = sanitize_exp_series(self._points, now)
        self._last_exp = result.last_exp
        self._gains = deque(result.gains)
        self._first_gain_at = result.first_gain_at
        self._last_gain_at = result.last_gain_at
        self._last_gain = result.last_gain

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
        self._refresh(now)
        cutoff = now - 86400
        while self._gains and self._gains[0][0] < cutoff:
            self._gains.popleft()

    def _append_history(self, now: float, exp: int) -> None:
        if self.history_path is None:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        stamped = _round_t(now)
        line = '{"t": %s, "exp": %d}\n' % (format(stamped, ".6f"), exp)
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

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
            self._points.append(ExpPoint(ts, exp))
            if self._started_at is None:
                self._started_at = ts
        if self._points:
            last_t = self._points[-1].t
            self._refresh(last_t)
            self._prune(last_t)
