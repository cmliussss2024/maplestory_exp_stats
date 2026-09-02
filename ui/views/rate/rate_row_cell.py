"""One rate metric: caption, value, and unit."""

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
        caption: str,
        variable: tk.StringVar,
        unit: str,
        value_unit_gap: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        caption_label = ttk.Label(
            self,
            text=caption,
            font=Type.Rate.caption,
            foreground=Type.Rate.caption_color,
        )
        caption_label.pack(anchor="w")
        self.register_theme_label(caption_label, "text_secondary")
        values = Panel(self, use_debug=False)
        values.pack(anchor="w")
        value_label = ttk.Label(
            values,
            textvariable=variable,
            font=Type.Rate.value,
            foreground=Type.Rate.value_color,
        )
        value_label.pack(side="left")
        self.register_theme_label(value_label, "text_primary")
        unit_label = ttk.Label(
            values,
            text=unit,
            font=Type.Rate.unit,
            foreground=Type.Rate.unit_color,
        )
        unit_label.pack(side="left", padx=(value_unit_gap, 0))
        self.register_theme_label(unit_label, "text_tertiary")
