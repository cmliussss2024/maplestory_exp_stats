"""Base panel frame with optional debug background."""

from __future__ import annotations

import tkinter as tk

from ui import theme
from ui.debug import DEBUG_PANELS, debug_bg

# Registered ttk labels are repainted as ``(widget, palette_key)`` pairs.
ThemeLabel = tuple[tk.Widget, str]


def apply_widget_theme(widget: tk.Misc) -> None:
    """Recursively repaint ``widget`` and its subtree from the active palette.

    Widgets that define an ``apply_theme`` method own their full repaint.
    Plain tk frames without one get the theme background directly.
    """
    method = getattr(widget, "apply_theme", None)
    if method is not None:
        method()
        return
    if widget.winfo_class() == "Frame":
        try:
            widget.configure(bg=theme.palette().bg)
        except tk.TclError:
            pass
    for child in widget.winfo_children():
        apply_widget_theme(child)


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
        self._theme_labels: list[ThemeLabel] = []

    def register_theme_label(self, label: tk.Widget, key: str) -> None:
        """Remember a ttk label so theme switches can repaint its foreground."""
        self._theme_labels.append((label, key))

    def apply_theme(self) -> None:
        """Repaint this panel, its registered labels, and all descendants."""
        p = theme.palette()
        try:
            self.configure(bg=p.bg)
        except tk.TclError:
            pass
        for label, key in self._theme_labels:
            try:
                label.configure(foreground=getattr(p, key))
            except tk.TclError:
                pass
        for child in self.winfo_children():
            apply_widget_theme(child)
