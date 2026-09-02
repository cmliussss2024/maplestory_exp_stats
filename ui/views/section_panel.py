"""Padded section. Pass split=True for two side-by-side panes."""

from __future__ import annotations

import tkinter as tk

from ui.debug import DEBUG_PANELS, DEBUG_SECTION_BG_RGB
from ui.styles import Spacing, Type
from ui.views.panel import Panel


class SectionPanel(Panel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        split: bool = False,
        **kwargs,
    ) -> None:
        kwargs.pop("use_debug", None)
        kwargs.pop("debug_rgb", None)
        super().__init__(
            master,
            use_debug=DEBUG_PANELS,
            debug_rgb=DEBUG_SECTION_BG_RGB,
            **kwargs,
        )
        pad = Spacing.section_padding
        if split:
            self._init_split()
            return
        self.content = Panel(self, use_debug=False)
        self.content.pack(fill="both", expand=True, padx=pad.padx, pady=pad.pady)

    def _init_split(self) -> None:
        self.columnconfigure(0, weight=1, uniform="half")
        self.columnconfigure(2, weight=1, uniform="half")
        self._divider = tk.Canvas(
            self,
            width=Spacing.divider_width,
            highlightthickness=0,
            bd=0,
            bg=Type.divider,
        )
        self._divider.place(relx=0.5, y=0, anchor="n")
        self.bind("<Configure>", self.sync_divider, add="+")

    def sync_divider(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "_divider"):
            return
        height = self.winfo_height()
        if height <= 1 or height == getattr(self, "_divider_h", None):
            return
        self._divider_h = height
        self._divider.configure(height=height)
        self._divider.place(
            relx=0.5,
            y=0,
            anchor="n",
            height=height,
            width=Spacing.divider_width,
        )
        self._divider.delete("all")
        self._divider.create_line(0, 0, 0, height, fill=Type.divider)

    def apply_theme(self) -> None:
        super().apply_theme()
        if not hasattr(self, "_divider"):
            return
        self._divider.configure(bg=Type.divider)
        height = self.winfo_height()
        self._divider.delete("all")
        if height > 1:
            self._divider.create_line(0, 0, 0, height, fill=Type.divider)
