from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


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


# Keep in sync with docs/charts.md
@dataclass(frozen=True)
class ChartSpec:
    title: str
    count: int
    step: float
    axis_start: str
    suffix: str
    mode: str
    source: str


CHARTS = (
    ChartSpec("效率", 300, 1.0, "5分钟前", "/秒", "per_sec_rate", "current"),
    ChartSpec("累计经验", 60, 60.0, "1小时前", "", "cumulative", "session"),
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
    if len(base_s) <= 1:
        return False
    trimmed_s = base_s[:-1]
    trimmed = int(trimmed_s)
    if trimmed <= 0 or reading < trimmed:
        return False
    inflated_cap = trimmed * 10 + 9
    if baseline > inflated_cap:
        return False
    if reading < trimmed * 1.01:
        return False
    if reading - trimmed <= 100:
        return False
    return reading - trimmed <= max(int(trimmed * 0.15), 5000)


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


def _rate_denom(elapsed: float | None, gained: int) -> float | None:
    if elapsed is None or elapsed <= 0 or gained <= 0:
        return None
    return max(elapsed, 1.0)


def rates_from_elapsed(gained: int, elapsed: float | None) -> Rates:
    denom = _rate_denom(elapsed, gained)
    if denom is None:
        return Rates(0, 0, 0, 0)
    return Rates(
        per_sec=int(round(gained / denom)),
        per_min=int(round(gained * 60.0 / denom)),
        per_5min=int(round(gained * 300.0 / denom)),
        per_hour=int(round(gained * 3600.0 / denom)),
    )


def sanitize_exp_series(points: Sequence[ExpPoint], now: float) -> SanitizedExp:
    if not points:
        return SanitizedExp(None, (), None, None)

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
    return SanitizedExp(last_exp, tuple(gains), first_gain_at, last_gain_at)


class RateTracker:
    LEVEL_CONFIRM_SECONDS = LEVEL_CONFIRM_SECONDS
    IDLE_CLEAR_SECONDS = 60.0

    def __init__(self, history_path: Path | None = None) -> None:
        self.history_path = Path(history_path) if history_path else None
        self._points: list[ExpPoint] = []
        self._last_exp: int | None = None
        self._first_gain_at: float | None = None
        self._last_gain_at: float | None = None
        self._paused: float = 0.0
        self._resumed_at: float | None = None
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
        return rates_from_elapsed(self.total_gained(), self._elapsed_at(now))

    def elapsed_since_first_gain(self, now: float) -> float | None:
        self._refresh(now)
        return self._elapsed_at(now)

    def _elapsed_at(self, now: float) -> float | None:
        if self._first_gain_at is None:
            return None
        elapsed = now - self._first_gain_at
        if (
            self._resumed_at is not None
            and self._first_gain_at < self._resumed_at
            and now >= self._resumed_at
        ):
            elapsed -= self._paused
        return max(elapsed, 0.0)

    def total_gained(self) -> int:
        return sum(delta for _ts, delta in self._gains)

    def clear(self) -> None:
        self._points.clear()
        self._last_exp = None
        self._first_gain_at = None
        self._last_gain_at = None
        self._paused = 0.0
        self._resumed_at = None
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

    def _record(self, exp: int | None, now: float) -> None:
        if exp is None:
            return
        stamped = _round_t(now)
        if self._points and self._points[-1].exp == exp:
            return
        self._points.append(ExpPoint(stamped, exp))
        self._append_history(stamped, exp)

    def _refresh(self, now: float) -> None:
        result = sanitize_exp_series(self._points, now)
        self._last_exp = result.last_exp
        self._gains = deque(result.gains)
        self._first_gain_at = result.first_gain_at
        self._last_gain_at = result.last_gain_at

    def chart_series(self, now: float, spec: ChartSpec) -> list[int]:
        self._refresh(now)
        times = [now - (spec.count - 1 - i) * spec.step for i in range(spec.count)]
        if spec.mode == "per_sec_rate":
            return self._per_sec_rate_values(times)
        return self._cumulative_values(times)

    def _gained_by(self, times: list[float]) -> list[int]:
        gains = list(self._gains)
        idx = 0
        running = 0
        values: list[int] = []
        for sample in times:
            while idx < len(gains) and gains[idx][0] <= sample:
                running += gains[idx][1]
                idx += 1
            values.append(running)
        return values

    def _per_sec_rate_values(self, times: list[float]) -> list[int]:
        return [
            rates_from_elapsed(running, self._elapsed_at(sample)).per_sec
            for sample, running in zip(times, self._gained_by(times))
        ]

    def _cumulative_values(self, times: list[float]) -> list[int]:
        return self._gained_by(times)

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
                ts = float(item["t"])
                exp = int(item["exp"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            self._points.append(ExpPoint(ts, exp))
        if self._points:
            last_t = self._points[-1].t
            self._refresh(last_t)
            resumed = time.time()
            gap = resumed - last_t
            if gap > 0:
                self._paused = gap
                self._resumed_at = resumed


def eta_to_level(
    current_exp: int | None,
    percent: float | None,
    gained: int,
    elapsed: float | None,
) -> float | None:
    if current_exp is None or current_exp <= 0:
        return None
    if percent is None or percent <= 0:
        return None
    if elapsed is None or elapsed <= 0 or gained <= 0:
        return None
    remaining = current_exp * (100.0 - percent) / percent
    if remaining <= 0:
        return 0.0
    denom = _rate_denom(elapsed, gained)
    if denom is None:
        return None
    return remaining * denom / gained
