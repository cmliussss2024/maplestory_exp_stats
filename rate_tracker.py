from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rates:
    per_second: int
    per_minute: int
    per_hour: int


class RateTracker:
    def __init__(
        self,
        mode: str = "realtime",
        history_path: Path | None = None,
    ) -> None:
        self.mode = mode
        self.history_path = Path(history_path) if history_path else None
        self._last_exp: int | None = None
        self._started_at: float | None = None
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
        return self.compute(now, self.mode)

    def compute(self, now: float, mode: str | None = None) -> Rates:
        mode = mode or self.mode
        self._prune(now)
        if mode == "average":
            return self._average_rates(now)
        return self._realtime_rates(now)

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
            if self._is_level_up(self._last_exp, exp):
                self._last_exp = exp
                if persist:
                    self._append_history(now, exp, 0)
            return
        if exp == self._last_exp:
            return
        if not self._plausible_gain(self._last_exp, exp):
            return
        delta = exp - self._last_exp
        self._gains.append((now, delta))
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

    @staticmethod
    def _plausible_gain(previous: int, new: int) -> bool:
        delta = new - previous
        if delta <= 0:
            return False
        if previous >= 1000 and delta > previous:
            return False
        return True

    def _realtime_rates(self, now: float) -> Rates:
        minute_sum = self._sum_since(now - 60)
        per_second = 0
        per_minute = 0
        per_hour = 0
        if self._last_gain_at is not None:
            idle = now - self._last_gain_at
            if idle <= 15:
                per_second = self._last_gain
            if idle <= 60:
                per_minute = minute_sum
            if idle <= 300:
                per_hour = minute_sum * 60 if idle <= 60 else self._hour_from_last_minute(now)
        return Rates(per_second, per_minute, per_hour)

    def _hour_from_last_minute(self, now: float) -> int:
        if self._last_gain_at is None:
            return 0
        window_end = self._last_gain_at
        return self._sum_between(window_end - 60, window_end) * 60

    def _average_rates(self, now: float) -> Rates:
        if self._started_at is None:
            return Rates(0, 0, 0)
        elapsed = max(now - self._started_at, 1.0)
        last_minute = self._sum_since(now - 60)
        last_hour = self._sum_since(now - 3600)
        last_day = self._sum_since(now - 86400)
        second_span = min(60.0, elapsed)
        minute_span = min(3600.0, elapsed)
        hour_span = min(86400.0, elapsed)
        return Rates(
            per_second=round(last_minute / second_span),
            per_minute=round(last_hour / minute_span * 60),
            per_hour=round(last_day / hour_span * 3600),
        )

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
            self._prune(self._gains[-1][0])
