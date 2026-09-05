"""Padded section with a single content pane."""

from __future__ import annotations

import tkinter as tk

from ui.debug import DEBUG_PANELS, DEBUG_SECTION_BG_RGB
from ui.styles import Spacing
from ui.views.panel import Panel


class SectionPanel(Panel):
    def __init__(
        self,
        master: tk.Misc,
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
        self.content = Panel(self, use_debug=False)
        self.content.pack(fill="both", expand=True, padx=pad.padx, pady=pad.pady)
