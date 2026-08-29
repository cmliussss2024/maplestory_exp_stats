"""Chart cards stacked without span tabs."""

from __future__ import annotations

from typing import Any

import tkinter as tk

from rate_tracker import CHARTS
from ui.styles import Spacing
from ui.views.chart.chart_card_panel import ChartCardPanel
from ui.views.panel import Panel
from ui.views.section_panel import SectionPanel


class ChartSectionPanel(SectionPanel):
    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.body = Panel(self.content, use_debug=False)
        self.body.pack(fill="x")

        self.gain_card = ChartCardPanel(
            self.body,
            title=CHARTS[0].title,
            bottom_pad=Spacing.Chart.gain_bottom_pad,
        )
        self.gain_card.pack(fill="x")

        self.total_card = ChartCardPanel(
            self.body,
            title=CHARTS[1].title,
            bottom_pad=Spacing.Chart.total_bottom_pad,
        )
        self.total_card.pack(fill="x")

    @property
    def gain_chart(self) -> tk.Canvas:
        return self.gain_card.canvas

    @property
    def total_chart(self) -> tk.Canvas:
        return self.total_card.canvas
