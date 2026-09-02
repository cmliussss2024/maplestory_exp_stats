"""效率 section: per-period rates and reset."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk

from ui.views.rate.rate_column_panel import RateColumnPanel
from ui.views.section_panel import SectionPanel


class RateSectionPanel(SectionPanel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        current_vars: dict[str, tk.StringVar],
        on_clear_current: Callable[[], None],
        on_float: Callable[[], None],
        on_toggle_theme: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.forecast = RateColumnPanel(
            self.content,
            vars_map=current_vars,
            on_clear=on_clear_current,
            on_float=on_float,
            on_toggle_theme=on_toggle_theme,
        )
        self.forecast.pack(fill="x")
        self.theme_button = self.forecast.theme_button
