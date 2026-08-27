"""Panel debug backgrounds."""

from __future__ import annotations

import tkinter as tk

# Toggle component background highlights for layout debugging.
DEBUG_PANELS = False
DEBUG_BG_RGB = (255, 255, 0)
DEBUG_SECTION_BG_RGB = (0, 255, 0)
DEBUG_BG_ALPHA = 0.3


def debug_bg(
    widget: tk.Misc,
    fallback: str,
    *,
    rgb: tuple[int, int, int] = DEBUG_BG_RGB,
) -> str:
    """Blend `rgb` over `fallback` at DEBUG_BG_ALPHA."""
    src_r, src_g, src_b = rgb
    alpha = DEBUG_BG_ALPHA
    try:
        r, g, b = widget.winfo_rgb(fallback)
        r, g, b = r // 256, g // 256, b // 256
    except tk.TclError:
        r, g, b = 240, 240, 240
    return "#{:02x}{:02x}{:02x}".format(
        round(src_r * alpha + r * (1 - alpha)),
        round(src_g * alpha + g * (1 - alpha)),
        round(src_b * alpha + b * (1 - alpha)),
    )
