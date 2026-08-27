"""Main window layout from composable panels."""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk

from ui.views.chart import ChartSectionPanel
from ui.views.hairline import Hairline
from ui.views.info import InfoSectionPanel
from ui.views.menu_bar_cell import MenuBarCell
from ui.views.rate import RateSectionPanel


class ExpRateWindow:
    def __init__(
        self,
        root: tk.Tk,
        *,
        current_vars: dict[str, tk.StringVar],
        session_vars: dict[str, tk.StringVar],
        current_exp: tk.StringVar,
        session_exp: tk.StringVar,
        session_time: tk.StringVar,
        status: tk.StringVar,
        on_clear_current: Callable[[], None],
        on_clear_session: Callable[[], None],
        on_retry: Callable[[], None],
        on_tab_select: Callable[[int], None],
        on_float: Callable[[], None],
    ) -> None:
        root.columnconfigure(0, weight=1)

        self.menu_bar = MenuBarCell(root, on_float=on_float)
        self.menu_bar.grid(row=0, column=0, sticky="ew")

        Hairline(root).grid(row=1, column=0, sticky="ew")

        self.rate_section = RateSectionPanel(
            root,
            current_vars=current_vars,
            session_vars=session_vars,
            on_clear_current=on_clear_current,
            on_clear_session=on_clear_session,
        )
        self.rate_section.grid(row=2, column=0, sticky="ew")

        Hairline(root).grid(row=3, column=0, sticky="ew")

        self.info_section = InfoSectionPanel(
            root,
            current_exp=current_exp,
            session_exp=session_exp,
            session_time=session_time,
            status=status,
            on_retry=on_retry,
        )
        self.info_section.grid(row=4, column=0, sticky="ew")
        self.retry_row = self.info_section.retry_row

        Hairline(root).grid(row=5, column=0, sticky="ew")

        self.chart_section = ChartSectionPanel(
            root,
            on_tab_select=on_tab_select,
        )
        self.chart_section.grid(row=6, column=0, sticky="ew")
