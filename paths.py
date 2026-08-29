"""Resolve bundled assets vs writable data for source and frozen runs."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Read-only files: PyInstaller `_MEIPASS` (`_internal/`) or the repo root."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def writable_root() -> Path:
    """Folder next to the exe when frozen, otherwise the repo root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def assets_dir() -> Path:
    return resource_root() / "assets"


def data_dir() -> Path:
    return writable_root() / "data"
