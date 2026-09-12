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
            font=Type.Chart.title,
            foreground=Type.Chart.title_color,
        )
        self._title.pack(anchor="w", pady=(0, Spacing.Chart.title_pad_bottom))
        self.register_theme_label(self._title, "text_primary")
        self.canvas = tk.Canvas(
            self,
            width=Spacing.Chart.width,
            height=Spacing.Chart.height,
            background=Type.Chart.canvas_bg,
            highlightthickness=1,
            highlightbackground=Type.Chart.canvas_border,
        )
        self.canvas.pack(pady=(0, bottom_pad))

    def apply_theme(self) -> None:
        super().apply_theme()
        self.canvas.configure(
            background=Type.Chart.canvas_bg,
            highlightbackground=Type.Chart.canvas_border,
        )
