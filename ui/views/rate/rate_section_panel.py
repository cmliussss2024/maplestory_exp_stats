"""Forecast and session rate columns."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk

from ui.styles import Spacing
from ui.views.rate.rate_column_panel import RateColumnPanel
from ui.views.section_panel import SectionPanel


class RateSectionPanel(SectionPanel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        current_vars: dict[str, tk.StringVar],
        session_vars: dict[str, tk.StringVar],
        on_clear_current: Callable[[], None],
        on_clear_session: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, split=True, **kwargs)
        pad = Spacing.section_padding
        self.forecast = RateColumnPanel(
            self,
            title="预估",
            vars_map=current_vars,
            on_clear=on_clear_current,
            value_unit_gap=Spacing.forecast_value_unit_gap,
            clear_pad_y=Spacing.forecast_clear_pad_y,
        )
        self.forecast.grid(row=0, column=0, sticky="nsew", padx=pad.padx, pady=pad.pady)
        self.session = RateColumnPanel(
            self,
            title="累计",
            vars_map=session_vars,
            on_clear=on_clear_session,
            value_unit_gap=Spacing.session_value_unit_gap,
            clear_pad_y=Spacing.session_clear_pad_y,
        )
        self.session.grid(row=0, column=2, sticky="nsew", padx=pad.padx, pady=pad.pady)
