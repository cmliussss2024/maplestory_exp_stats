"""Top bar with the float-mode button."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tkinter import ttk

from ui.styles import Spacing
from ui.views.panel import Panel


class MenuBarCell(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_float: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        ttk.Button(self, text="浮窗", command=on_float).pack(
            side="right",
            padx=Spacing.menu_bar_pad_x,
            pady=Spacing.menu_bar_pad_y,
        )
