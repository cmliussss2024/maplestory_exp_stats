"""Base panel frame with optional debug background."""

from __future__ import annotations

import tkinter as tk

from ui.debug import DEBUG_PANELS, debug_bg


class Panel(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        use_debug: bool | None = None,
        debug_rgb: tuple[int, int, int] | None = None,
        bg: str | None = None,
        **kwargs,
    ) -> None:
        enabled = DEBUG_PANELS if use_debug is None else use_debug
        if bg is None:
            try:
                bg = str(master.cget("bg"))
            except tk.TclError:
                bg = "SystemButtonFace"
        if enabled:
            extra = {} if debug_rgb is None else {"rgb": debug_rgb}
            bg = debug_bg(master, bg, **extra)
        super().__init__(
            master,
            bg=bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
