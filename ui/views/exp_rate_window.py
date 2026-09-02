"""Main window layout from composable panels."""

from __future__ import annotations

from collections.abc import Callable

import ctypes
import tkinter as tk
from tkinter import ttk

from ui import theme
from ui.views.chart import ChartSectionPanel
from ui.views.hairline import Hairline
from ui.views.info import InfoSectionPanel
from ui.views.cumulative import CumulativeSectionPanel
from ui.views.panel import apply_widget_theme
from ui.views.rate import RateSectionPanel


def _set_dark_titlebar(hwnd: int, enable: bool) -> None:
    """Tell DWM to draw the title bar in dark mode (Windows 10 1903+, 11 22H2+).

    ``enable=True`` makes the system chrome match a dark window background;
    ``enable=False`` restores the default light chrome. The Windows 11 22H2
    release switched the attribute ID from 19 to 20, so we try both.
    """
    try:
        value = ctypes.c_int(1 if enable else 0)
        size = ctypes.sizeof(value)
        for attribute in (19, 20):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), size,
            )
            if result == 0:
                return
    except (AttributeError, OSError):
        # dwmapi unavailable on non-Windows or stripped-down Python builds.
        pass


def _root_hwnd(root: tk.Tk) -> int:
    """Return the top-level window handle for Tk's root window."""
    try:
        return int(root.frame(), 16)
    except (tk.TclError, ValueError):
        return 0


class ExpRateWindow:
    def __init__(
        self,
        root: tk.Tk,
        *,
        current_vars: dict[str, tk.StringVar],
        current_exp: tk.StringVar,
        current_percent: tk.StringVar,
        session_exp: tk.StringVar,
        session_time: tk.StringVar,
        session_rate: tk.StringVar,
        level_eta: tk.StringVar,
        status: tk.StringVar,
        status_detail: tk.StringVar,
        on_clear_current: Callable[[], None],
        on_clear_session: Callable[[], None],
        on_retry: Callable[[], None],
        on_float: Callable[[], None],
        on_toggle_theme: Callable[[], None],
    ) -> None:
        self.root = root
        root.columnconfigure(0, weight=1)

        # "clam" is a pure-Tk theme whose colors follow ttk style options.
        # The default Windows "vista" theme draws buttons natively and ignores
        # style background/foreground, so buttons could never follow the theme.
        ttk.Style().theme_use("clam")

        self.rate_section = RateSectionPanel(
            root,
            current_vars=current_vars,
            on_clear_current=on_clear_current,
            on_float=on_float,
            on_toggle_theme=on_toggle_theme,
        )
        self.rate_section.grid(row=0, column=0, sticky="ew")
        self.theme_button = self.rate_section.theme_button

        Hairline(root).grid(row=1, column=0, sticky="ew")

        self.cumulative_section = CumulativeSectionPanel(
            root,
            session_exp=session_exp,
            session_time=session_time,
            session_rate=session_rate,
            level_eta=level_eta,
            on_clear_session=on_clear_session,
        )
        self.cumulative_section.grid(row=2, column=0, sticky="ew")

        Hairline(root).grid(row=3, column=0, sticky="ew")

        self.info_section = InfoSectionPanel(
            root,
            current_exp=current_exp,
            current_percent=current_percent,
            status=status,
            status_detail=status_detail,
            on_retry=on_retry,
        )
        self.info_section.grid(row=4, column=0, sticky="ew")
        self.retry_row = self.info_section.retry_row

        Hairline(root).grid(row=5, column=0, sticky="ew")

        self.chart_section = ChartSectionPanel(root)
        self.chart_section.grid(row=6, column=0, sticky="ew")

        self.apply_theme()

    def apply_theme(self) -> None:
        """Repaint every widget, shared ttk style, and the theme button."""
        p = theme.palette()
        try:
            self.root.configure(bg=p.bg)
        except tk.TclError:
            pass
        style = ttk.Style()
        style.configure(
            "Theme.TButton",
            background=p.btn_bg,
            foreground=p.btn_fg,
            bordercolor=p.btn_border,
            lightcolor=p.btn_bg,
            darkcolor=p.btn_bg,
            focuscolor=p.btn_bg,
            relief="flat",
            borderwidth=1,
            padding=(8, 3),
        )
        style.map(
            "Theme.TButton",
            background=[
                ("disabled", p.btn_disabled_bg),
                ("pressed", p.btn_pressed_bg),
                ("active", p.btn_hover_bg),
            ],
            foreground=[("disabled", p.btn_disabled_fg)],
            bordercolor=[
                ("disabled", p.btn_border),
                ("pressed", p.btn_border),
                ("active", p.btn_border),
            ],
        )
        style.configure("TFrame", background=p.bg)
        style.configure("TLabel", background=p.bg)
        for child in self.root.winfo_children():
            apply_widget_theme(child)
        self.theme_button.configure(text=theme.toggle_label())
        hwnd = _root_hwnd(self.root)
        if hwnd:
            _set_dark_titlebar(hwnd, theme.current_theme() == "dark")
