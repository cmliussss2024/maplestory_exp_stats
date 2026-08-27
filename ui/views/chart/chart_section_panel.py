"""Chart tabs plus stacked gain and total cards."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk

from rate_tracker import CHART_TABS
from ui.styles import Spacing
from ui.views.chart.chart_card_panel import ChartCardPanel
from ui.views.chart.chart_tab_bar_cell import ChartTabBarCell
from ui.views.panel import Panel
from ui.views.section_panel import SectionPanel


class ChartSectionPanel(SectionPanel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_tab_select: Callable[[int], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.tab_bar = ChartTabBarCell(
            self.content,
            root_bg=str(self.cget("bg")),
            on_select=on_tab_select,
        )
        self.tab_bar.pack()

        self.body = Panel(self.content, use_debug=False)
        self.body.pack(fill="x")

        self.gain_card = ChartCardPanel(
            self.body,
            title=CHART_TABS[0][6],
            bottom_pad=Spacing.gain_chart_bottom_pad,
        )
        self.gain_card.pack(fill="x")

        self.total_card = ChartCardPanel(
            self.body,
            title="累计经验",
            bottom_pad=Spacing.total_chart_bottom_pad,
        )
        self.total_card.pack(fill="x")

    @property
    def gain_chart(self) -> tk.Canvas:
        return self.gain_card.canvas

    @property
    def total_chart(self) -> tk.Canvas:
        return self.total_card.canvas

    def set_gain_title(self, title: str) -> None:
        self.gain_card.set_title(title)

    def draw_tabs(self, selected: int) -> None:
        self.tab_bar.draw(selected)
