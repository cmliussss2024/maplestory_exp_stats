"""Chart span tab bar."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk

from rate_tracker import CHART_TABS
from ui.drawing import render_segmented_tab
from ui.styles import Spacing, Type
from ui.views.panel import Panel


class ChartTabBarCell(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        root_bg: str,
        on_select: Callable[[int], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self._selected = 0
        self._photo = None
        self._on_select = on_select
        self.canvas = tk.Canvas(
            self,
            width=Spacing.chart_width,
            height=Spacing.tab_bar_height,
            highlightthickness=0,
            bd=0,
            bg=root_bg,
            cursor="hand2",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)

    def _on_click(self, event: tk.Event) -> None:
        index = 0 if event.x < Spacing.chart_width // 2 else 1
        self._on_select(index)

    def draw(self, selected: int) -> None:
        self._selected = selected
        canvas = self.canvas
        canvas.delete("all")
        width = Spacing.chart_width
        height = Spacing.tab_bar_height
        self._photo = render_segmented_tab(
            canvas,
            width,
            height,
            Spacing.tab_radius,
            selected,
            bg=str(canvas.cget("bg")),
            track=Type.tab_track,
            active=Type.tab_active_bg,
            border=Type.tab_border,
            inset=Spacing.tab_inset,
        )
        canvas.create_image(0, 0, image=self._photo, anchor="nw")

        for index, (label, *_rest) in enumerate(CHART_TABS):
            x = width // 4 if index == 0 else width * 3 // 4
            is_active = index == selected
            canvas.create_text(
                x,
                height // 2,
                text=label,
                fill=Type.tab_active_text if is_active else Type.tab_text,
                font=Type.tab_active if is_active else Type.tab,
            )
