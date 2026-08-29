"""Caption on the left, value on the right, optional unit."""

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from ui.styles import Type
from ui.views.panel import Panel


class CumulativeRowCell(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        caption: str,
        variable: tk.StringVar,
        unit: str = "",
        value_unit_gap: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        ttk.Label(
            self,
            text=caption,
            font=Type.Cumulative.caption,
            foreground=Type.Cumulative.caption_color,
        ).pack(side="left")
        if unit:
            ttk.Label(
                self,
                text=unit,
                font=Type.Cumulative.unit,
                foreground=Type.Cumulative.unit_color,
            ).pack(side="right")
        ttk.Label(
            self,
            textvariable=variable,
            font=Type.Cumulative.value,
            foreground=Type.Cumulative.value_color,
        ).pack(side="right", padx=(0, value_unit_gap) if unit else 0)
