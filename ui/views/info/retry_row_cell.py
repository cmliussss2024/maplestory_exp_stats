"""Retry locator button row."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk
from tkinter import ttk

from ui.views.panel import Panel


class RetryRowCell(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_retry: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.button = ttk.Button(
            self,
            text="重新监听",
            command=on_retry,
            state="disabled",
            style="Theme.TButton",
        )
        self.button.pack(anchor="e")
