"""One rate value plus its unit label."""

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from ui.styles import Type
from ui.views.panel import Panel


class RateRowCell(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        variable: tk.StringVar,
        unit: str,
        value_unit_gap: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        ttk.Label(
            self,
            text=unit,
            font=Type.rate_unit,
            foreground=Type.rate_unit_color,
        ).pack(side="right")
        ttk.Label(
            self,
            textvariable=variable,
            font=Type.rate_value,
            foreground=Type.rate_value_color,
        ).pack(side="right", padx=(0, value_unit_gap))
