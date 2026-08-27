"""1px section divider without ttk groove chrome."""

from __future__ import annotations

import tkinter as tk

from ui.styles import Type


class Hairline(tk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(
            master,
            height=1,
            bg=Type.divider,
            highlightthickness=0,
            bd=0,
        )
