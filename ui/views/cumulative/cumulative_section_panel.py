"""累计 section: exp, time, hourly gain, and reset."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk

from ui.views.cumulative.cumulative_column_panel import CumulativeColumnPanel
from ui.views.section_panel import SectionPanel


class CumulativeSectionPanel(SectionPanel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        session_exp: tk.StringVar,
        session_time: tk.StringVar,
        session_rate: tk.StringVar,
        level_eta: tk.StringVar,
        on_clear_session: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.body = CumulativeColumnPanel(
            self.content,
            session_exp=session_exp,
            session_time=session_time,
            session_rate=session_rate,
            level_eta=level_eta,
            on_clear=on_clear_session,
        )
        self.body.pack(fill="x")
