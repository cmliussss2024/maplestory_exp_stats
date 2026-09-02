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
        caption_label = ttk.Label(
            self,
            text=caption,
            font=Type.Cumulative.caption,
            foreground=Type.Cumulative.caption_color,
        )
        caption_label.pack(side="left")
        self.register_theme_label(caption_label, "text_primary")
        if unit:
            unit_label = ttk.Label(
                self,
                text=unit,
                font=Type.Cumulative.unit,
                foreground=Type.Cumulative.unit_color,
            )
            unit_label.pack(side="right")
            self.register_theme_label(unit_label, "text_tertiary")
        value_label = ttk.Label(
            self,
            textvariable=variable,
            font=Type.Cumulative.value,
            foreground=Type.Cumulative.value_color,
        )
        value_label.pack(side="right", padx=(0, value_unit_gap) if unit else 0)
        self.register_theme_label(value_label, "text_primary")
