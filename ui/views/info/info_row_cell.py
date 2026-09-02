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
        caption_label = ttk.Label(
            self,
            text=caption,
            font=Type.Info.label,
            foreground=Type.Info.label_color,
        )
        caption_label.pack(side="left")
        self.register_theme_label(caption_label, "text_primary")
        if detail is not None:
            detail_label = ttk.Label(
                self,
                textvariable=detail,
                font=Type.Info.detail,
                foreground=Type.Info.detail_color,
            )
            detail_label.pack(side="right")
            self.register_theme_label(detail_label, "text_tertiary")
        self.value_label = ttk.Label(
            self,
            textvariable=variable,
            font=Type.Info.value,
            foreground=Type.Info.value_color,
        )
        self.value_label.pack(side="right", padx=(0, 4) if detail is not None else 0)
        self.register_theme_label(self.value_label, "text_primary")
