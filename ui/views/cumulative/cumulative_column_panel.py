"""累计 totals: exp, time, hourly gain, and reset."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk
from tkinter import ttk

from ui.styles import Spacing, Type
from ui.views.cumulative.cumulative_row_cell import CumulativeRowCell
from ui.views.panel import Panel


class CumulativeColumnPanel(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        session_exp: tk.StringVar,
        session_time: tk.StringVar,
        session_rate: tk.StringVar,
        level_eta: tk.StringVar,
        on_clear: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, use_debug=False, **kwargs)
        # ttk.Label(
        #     self,
        #     text="累计",
        #     font=Type.Cumulative.header,
        #     foreground=Type.Cumulative.header_color,
        # ).pack(anchor="w")
        # ttk.Label(
        #     self,
        #     text="~",
        #     font=Type.Cumulative.hint,
        #     foreground=Type.Cumulative.hint_color,
        # ).pack(anchor="w", pady=Spacing.Cumulative.hint_pad_y)
        rows = (
            ("累计经验", session_exp, ""),
            ("累计时长", session_time, ""),
            ("时均收益", session_rate, "/时"),
            ("升级预估时间", level_eta, ""),
        )
        last = len(rows) - 1
        for index, (caption, variable, unit) in enumerate(rows):
            CumulativeRowCell(
                self,
                caption=caption,
                variable=variable,
                unit=unit,
                value_unit_gap=Spacing.Cumulative.value_unit_gap if unit else 0,
            ).pack(
                fill="x",
                pady=(0, Spacing.Cumulative.cell_spacing) if index < last else 0,
            )
        ttk.Button(self, text="重置", command=on_clear).pack(
            anchor="e",
            pady=(Spacing.Cumulative.clear_pad_y[0], 0),
        )
