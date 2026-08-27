"""Titled chart canvas card."""

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from ui.styles import Spacing, Type
from ui.views.panel import Panel


class ChartCardPanel(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        title: str,
        bottom_pad: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self._title = ttk.Label(
            self,
            text=title,
            font=Type.chart_title,
            foreground=Type.chart_title_color,
        )
        self._title.pack(anchor="w", pady=(0, Spacing.chart_title_pad_bottom))
        self.canvas = tk.Canvas(
            self,
            width=Spacing.chart_width,
            height=Spacing.chart_height,
            background=Type.chart_canvas_bg,
            highlightthickness=1,
            highlightbackground=Type.chart_canvas_border,
        )
        self.canvas.pack(pady=(0, bottom_pad))

    def set_title(self, title: str) -> None:
        self._title.configure(text=title)
