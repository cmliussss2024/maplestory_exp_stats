"""One rate column: title, rows, and clear button."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk
from tkinter import ttk

from rate_tracker import RATE_ROWS
from ui.styles import Spacing, Type
from ui.views.panel import Panel
from ui.views.rate.rate_row_cell import RateRowCell


class RateColumnPanel(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        title: str,
        vars_map: dict[str, tk.StringVar],
        on_clear: Callable[[], None],
        value_unit_gap: int,
        clear_pad_y: tuple[int, int],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, use_debug=False, **kwargs)
        ttk.Label(
            self,
            text=title,
            font=Type.rate_header,
            foreground=Type.rate_header_color,
        ).pack(anchor="e")
        last = len(RATE_ROWS) - 1
        for index, (key, unit) in enumerate(RATE_ROWS):
            RateRowCell(
                self,
                variable=vars_map[key],
                unit=unit,
                value_unit_gap=value_unit_gap,
            ).pack(
                anchor="e",
                pady=(0, Spacing.rate_cell_spacing) if index < last else 0,
            )
        ttk.Button(self, text="清空", command=on_clear).pack(
            anchor="e", pady=(clear_pad_y[0], 0),
        )
