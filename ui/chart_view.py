"""Chart canvas rendering."""

from __future__ import annotations

import tkinter as tk

from ui.styles import Spacing, Type


def fmt_value(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def chart_points(
    values: list[int],
    width: int,
    height: int,
    pad_x: int,
    pad_top: int,
    pad_bottom: int,
) -> list[tuple[int, int]]:
    if not values:
        return []
    inner_w = max(width - 2 * pad_x, 1)
    inner_h = max(height - pad_top - pad_bottom, 1)
    peak = max(max(values), 1)
    last = max(len(values) - 1, 1)
    points: list[tuple[int, int]] = []
    for index, value in enumerate(values):
        x = pad_x + inner_w * index / last
        y = pad_top + inner_h - inner_h * value / peak
        points.append((round(x), round(y)))
    return points


def paint_chart(
    canvas: tk.Canvas,
    values: list[int],
    *,
    suffix: str,
    line: str,
    fill: str,
    axis_start: str,
    axis_end: str = "现在",
    pad_x: int = Spacing.Chart.pad_x,
    pad_top: int = Spacing.Chart.pad_top,
    pad_bottom: int = Spacing.Chart.pad_bottom,
) -> None:
    width = int(canvas.cget("width"))
    height = int(canvas.cget("height"))
    peak = max(values) if values else 0
    current = values[-1] if values else 0
    points = chart_points(values, width, height, pad_x, pad_top, pad_bottom)

    canvas.delete("all")
    plot_right = width - pad_x
    plot_bottom = height - pad_bottom
    for frac in (0.0, 0.5, 1.0):
        y = pad_top + (plot_bottom - pad_top) * (1.0 - frac)
        canvas.create_line(pad_x, y, plot_right, y, fill=Type.Chart.grid)

    if len(points) >= 2:
        coords = [coord for point in points for coord in point]
        area = [
            *coords,
            points[-1][0],
            plot_bottom,
            points[0][0],
            plot_bottom,
        ]
        canvas.create_polygon(*area, fill=fill, outline="")
        canvas.create_line(*coords, fill=line, width=2)

    axis_y = height - Spacing.Chart.axis_label_y_offset
    canvas.create_text(
        pad_x,
        Spacing.Chart.caption_y,
        text=fmt_value(peak),
        anchor="w",
        fill=Type.Chart.peak,
        font=Type.Chart.caption,
    )
    canvas.create_text(
        plot_right,
        Spacing.Chart.caption_y,
        text=f"{fmt_value(current)}{suffix}",
        anchor="e",
        fill=line,
        font=Type.Chart.caption,
    )
    canvas.create_text(
        pad_x, axis_y, text=axis_start, anchor="w", fill=Type.Chart.axis, font=Type.Chart.caption,
    )
    canvas.create_text(
        plot_right, axis_y, text=axis_end, anchor="e", fill=Type.Chart.axis, font=Type.Chart.caption,
    )
