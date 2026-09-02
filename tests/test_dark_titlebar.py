"""Regression tests for the dark title-bar fix on first launch.

The OS chrome (title bar / min/max/close buttons) follows
``DwmSetWindowAttribute`` only when the window is already mapped to the
screen. On the very first paint the Tk root is not mapped yet, so the call
is silently dropped and the title bar stays light until the user toggles
the theme. ``ExpRateWindow._refresh_dark_titlebar`` is expected to defer
the second attempt until Tk reports the root as visible.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Headless test environments have no Tk; stub the modules the unit-under-
# test imports so we can exercise the pure control flow without a display.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

fake_tk = MagicMock()
fake_ttk = MagicMock()
sys.modules.setdefault("tkinter", fake_tk)
sys.modules.setdefault("tkinter.ttk", fake_ttk)

# Make every ``tkinter`` attribute a MagicMock so module-level aliases in
# exp_rate_window.py (``import tkinter as tk``) resolve without raising.
fake_tk.Tk = MagicMock()
fake_tk.TclError = type("TclError", (Exception,), {})
fake_tk.Event = type("Event", (), {})

from ui.views import exp_rate_window  # noqa: E402  (imports after stubbing)
from ui import theme as theme_module  # noqa: E402


class _RecordingHwnd:
    """Stand-in for the Tk root that records title-bar attribute writes."""

    def __init__(self) -> None:
        self.mapped = False
        self.titlebar_calls: list[bool] = []
        self.visibility_handlers: list = []

    def winfo_ismapped(self) -> bool:
        return self.mapped

    def bind(self, sequence: str, handler, add: str = "") -> None:
        if sequence == "<Visibility>":
            # Mirror Tk's real semantics: once a Visibility handler fires,
            # the window has just become mapped.
            def wrapped(event) -> None:
                self.mapped = True
                handler(event)

            self.visibility_handlers.append(wrapped)

    def unbind(self, sequence: str) -> None:
        if sequence == "<Visibility>":
            self.visibility_handlers.clear()


class DarkTitlebarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[bool] = []
        # Each test starts from a known dark-mode baseline so we can
        # observe the attribute being written without leaking state from
        # other test files that may have imported ``ui.theme``.
        theme_module.set_theme("dark")
        exp_rate_window._set_dark_titlebar = (
            lambda hwnd, enable: self.calls.append(enable)
        )
        exp_rate_window._root_hwnd = lambda root: 0xDEAD

    def test_unmapped_window_defers_until_visibility(self) -> None:
        root = _RecordingHwnd()
        window = exp_rate_window.ExpRateWindow.__new__(
            exp_rate_window.ExpRateWindow
        )
        window.root = root

        window._refresh_dark_titlebar()

        # First call drops because the window is not mapped yet.
        self.assertEqual(self.calls, [True])
        # A Visibility handler is registered exactly once.
        self.assertEqual(len(root.visibility_handlers), 1)

        # Now the window is mapped: the deferred handler must issue the
        # call a second time and tear down its own binding so it won't run
        # again on every future Visibility event.
        self.calls.clear()
        root.visibility_handlers[0](MagicMock(widget=root))
        self.assertEqual(self.calls, [True])
        self.assertEqual(root.visibility_handlers, [])

    def test_mapped_window_skips_visibility_binding(self) -> None:
        root = _RecordingHwnd()
        root.mapped = True
        window = exp_rate_window.ExpRateWindow.__new__(
            exp_rate_window.ExpRateWindow
        )
        window.root = root

        window._refresh_dark_titlebar()

        self.assertEqual(self.calls, [True])
        self.assertEqual(root.visibility_handlers, [])

    def test_follows_current_theme_when_visibility_fires(self) -> None:
        root = _RecordingHwnd()
        window = exp_rate_window.ExpRateWindow.__new__(
            exp_rate_window.ExpRateWindow
        )
        window.root = root

        window._refresh_dark_titlebar()
        # Pretend the user toggled to light before the window came up.
        theme_module.set_theme("light")
        root.mapped = True
        root.visibility_handlers[0](MagicMock(widget=root))

        self.assertEqual(self.calls, [True, False])


if __name__ == "__main__":
    unittest.main()