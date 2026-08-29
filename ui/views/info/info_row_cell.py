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
        detail: tk.StringVar | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        ttk.Label(
            self,
            text=caption,
            font=Type.Info.label,
            foreground=Type.Info.label_color,
        ).pack(side="left")
        if detail is not None:
            ttk.Label(
                self,
                textvariable=detail,
                font=Type.Info.detail,
                foreground=Type.Info.detail_color,
            ).pack(side="right")
        self.value_label = ttk.Label(
            self,
            textvariable=variable,
            font=Type.Info.value,
            foreground=Type.Info.value_color,
        )
        self.value_label.pack(side="right", padx=(0, 4) if detail is not None else 0)
