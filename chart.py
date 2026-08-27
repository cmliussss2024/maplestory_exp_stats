from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    open: int
    high: int
    low: int
    close: int


@dataclass(frozen=True)
class CandleGeom:
    x_center: int
    body_left: int
    body_right: int
    body_top: int
    body_bottom: int
    wick_top: int
    wick_bottom: int
    bullish: bool


def values_to_polyline(
    values: Sequence[int],
    width: int,
    height: int,
    padding: int = 12,
) -> list[tuple[int, int]]:
    if not values:
        return []
    inner_w = max(width - 2 * padding, 1)
    inner_h = max(height - 2 * padding, 1)
    peak = max(max(values), 1)
    last = max(len(values) - 1, 1)
    points: list[tuple[int, int]] = []
    for index, value in enumerate(values):
        x = padding + inner_w * index / last
        y = padding + inner_h - inner_h * value / peak
        points.append((round(x), round(y)))
    return points


def candles_to_geometry(
    candles: Sequence[Candle],
    width: int,
    height: int,
    padding: int = 12,
) -> list[CandleGeom]:
    if not candles:
        return []
    inner_w = max(width - 2 * padding, 1)
    inner_h = max(height - 2 * padding, 1)
    peak = max(max(candle.high for candle in candles), 1)
    slot = inner_w / len(candles)
    body_w = max(int(slot * 0.6), 1)
    geoms: list[CandleGeom] = []
    for index, candle in enumerate(candles):
        center = padding + slot * (index + 0.5)
        x_center = round(center)
        half = body_w // 2
        body_left = x_center - half
        body_right = body_left + max(body_w, 1)
        body_top = _y(max(candle.open, candle.close), peak, padding, inner_h)
        body_bottom = _y(min(candle.open, candle.close), peak, padding, inner_h)
        if body_bottom == body_top:
            body_bottom = min(body_top + 1, padding + inner_h)
        geoms.append(
            CandleGeom(
                x_center=x_center,
                body_left=body_left,
                body_right=body_right,
                body_top=body_top,
                body_bottom=body_bottom,
                wick_top=_y(candle.high, peak, padding, inner_h),
                wick_bottom=_y(candle.low, peak, padding, inner_h),
                bullish=candle.close >= candle.open,
            )
        )
    return geoms


def _y(value: int, peak: int, padding: int, inner_h: int) -> int:
    return round(padding + inner_h - inner_h * value / peak)
