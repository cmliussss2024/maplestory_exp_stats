"""Caption plus value on one info row."""

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from ui.styles import Type
from ui.views.panel import Panel


class InfoRowCell(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        caption: str,
        variable: tk.StringVar,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        ttk.Label(
            self,
            text=caption,
            font=Type.info_label,
            foreground=Type.info_label_color,
        ).pack(side="left")
        self.value_label = ttk.Label(
            self,
            textvariable=variable,
            font=Type.info_value,
            foreground=Type.info_value_color,
        )
        self.value_label.pack(side="right")
