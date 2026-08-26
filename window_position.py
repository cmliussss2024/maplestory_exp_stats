from __future__ import annotations

import json
from pathlib import Path


def load_window_position(path: Path) -> tuple[int, int] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return int(data["x"]), int(data["y"])
    except (KeyError, TypeError, ValueError):
        return None


def save_window_position(path: Path, x: int, y: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"x": int(x), "y": int(y)}), encoding="utf-8")
