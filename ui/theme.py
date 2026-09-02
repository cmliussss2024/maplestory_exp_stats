"""Theme palettes and persistence for the main window.

The overlay (浮窗) intentionally keeps its own black translucent look and is
not affected by theme switching.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from paths import data_dir

_VALID = ("light", "dark")


@dataclass(frozen=True)
class Palette:
    """Named colors used by the main window for one theme."""

    bg: str
    divider: str
    text_primary: str
    text_secondary: str
    text_tertiary: str
    chart_bg: str
    chart_border: str
    grid: str
    gain_line: str
    gain_fill: str
    total_line: str
    total_fill: str
    status_ok: str
    status_search: str
    status_error: str
    btn_bg: str
    btn_fg: str
    btn_border: str
    btn_hover_bg: str
    btn_pressed_bg: str
    btn_disabled_bg: str
    btn_disabled_fg: str


THEMES: dict[str, Palette] = {
    "light": Palette(
        bg="SystemButtonFace",
        divider="#d9d9d9",
        text_primary="#101010",
        text_secondary="#606060",
        text_tertiary="#9D9D9D",
        chart_bg="#f7f7f7",
        chart_border="#d0d0d0",
        grid="#e6e6e6",
        gain_line="#2e7d32",
        gain_fill="#c8e6c9",
        total_line="#1565c0",
        total_fill="#bbdefb",
        status_ok="#2e7d32",
        status_search="#e6a817",
        status_error="#c62828",
        btn_bg="#ececec",
        btn_fg="#101010",
        btn_border="#c8c8c8",
        btn_hover_bg="#e0e0e0",
        btn_pressed_bg="#d6d6d6",
        btn_disabled_bg="#ececec",
        btn_disabled_fg="#9D9D9D",
    ),
    "dark": Palette(
        bg="#1e1e1e",
        divider="#3a3a3a",
        text_primary="#e6e6e6",
        text_secondary="#a8a8a8",
        text_tertiary="#777777",
        chart_bg="#2a2a2a",
        chart_border="#444444",
        grid="#3a3a3a",
        gain_line="#66bb6a",
        gain_fill="#1b3a1c",
        total_line="#42a5f5",
        total_fill="#0d2a40",
        status_ok="#66bb6a",
        status_search="#ffb74d",
        status_error="#ef5350",
        btn_bg="#3a3a3a",
        btn_fg="#e6e6e6",
        btn_border="#555555",
        btn_hover_bg="#464646",
        btn_pressed_bg="#2f2f2f",
        btn_disabled_bg="#2a2a2a",
        btn_disabled_fg="#777777",
    ),
}

_current = "light"


def current_theme() -> str:
    """Return the active theme name, one of ``light`` or ``dark``."""
    return _current


def set_theme(name: str) -> None:
    """Switch the active theme; unknown names fall back to ``light``."""
    global _current
    _current = name if name in THEMES else "light"


def palette() -> Palette:
    """Return the palette of the active theme."""
    return THEMES[_current]


def toggle_label() -> str:
    """Text the theme button should show: the mode it switches *to*."""
    return "日间配色" if _current == "dark" else "夜间配色"


def _settings_path() -> Path:
    return data_dir() / "settings.json"


def load_preference() -> str:
    """Read the persisted theme name; missing/corrupt settings fall back."""
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "light"
    name = data.get("theme", "light")
    return name if name in THEMES else "light"


def save_preference(name: str) -> None:
    """Persist the ``theme`` field without removing other settings keys."""
    path = _settings_path()
    data: dict[str, object] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data["theme"] = name if name in THEMES else "light"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
