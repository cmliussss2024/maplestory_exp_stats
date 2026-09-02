"""效率 column: title, per-period rates, and reset."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk
from tkinter import ttk

from rate_tracker import RATE_ROWS
from ui import theme
from ui.styles import Spacing, Type
from ui.views.panel import Panel
from ui.views.rate.rate_row_cell import RateRowCell

_CAPTIONS = {
    "per_sec": "秒",
    "per_min": "分",
    "per_5min": "5分",
    "per_hour": "小时",
}


class RateColumnPanel(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        vars_map: dict[str, tk.StringVar],
        on_clear: Callable[[], None],
        on_float: Callable[[], None],
        on_toggle_theme: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, use_debug=False, **kwargs)
        header = Panel(self, use_debug=False)
        header.pack(fill="x")
        ttk.Button(
            header,
            text="浮窗",
            command=on_float,
            style="Theme.TButton",
        ).pack(side="right")
        self.theme_button = ttk.Button(
            header,
            text=theme.toggle_label(),
            command=on_toggle_theme,
            style="Theme.TButton",
        )
        self.theme_button.pack(side="right", padx=(0, 4))
        title_label = ttk.Label(
            header,
            text="收益",
            font=Type.Rate.header,
            foreground=Type.Rate.header_color,
        )
        title_label.pack(side="left")
        self.register_theme_label(title_label, "text_primary")
        hint_label = ttk.Label(
            self,
            text="1 分钟无增长则自动重置",
            font=Type.Rate.hint,
            foreground=Type.Rate.hint_color,
        )
        hint_label.pack(anchor="w", pady=Spacing.Rate.hint_pad_y)
        self.register_theme_label(hint_label, "text_tertiary")
        grid = Panel(self, use_debug=False)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1, uniform="rate")
        grid.columnconfigure(1, weight=1, uniform="rate")
        for index, (key, unit) in enumerate(RATE_ROWS):
            row, col = divmod(index, 2)
            RateRowCell(
                grid,
                caption=_CAPTIONS[key],
                variable=vars_map[key],
                unit=unit,
                value_unit_gap=Spacing.Rate.value_unit_gap,
            ).grid(
                row=row,
                column=col,
                sticky="ew",
                padx=(0, Spacing.Rate.grid_col_gap) if col == 0 else 0,
                pady=(0, Spacing.Rate.grid_row_gap) if row == 0 else 0,
            )
        ttk.Button(
            self,
            text="重置",
            command=on_clear,
            style="Theme.TButton",
        ).pack(
            anchor="e",
            pady=(Spacing.Rate.clear_pad_y[0], 0),
        )
