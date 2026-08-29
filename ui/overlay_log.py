"""Append-only debug log for overlay DPI / resize issues."""

from __future__ import annotations

import time

from paths import data_dir

LOG_PATH = data_dir() / "overlay-debug.log"


def overlay_log(event: str, **fields: object) -> None:
    stamp = time.strftime("%H:%M:%S")
    millis = int((time.time() % 1) * 1000)
    parts = [f"{stamp}.{millis:03d}", event]
    for key, value in fields.items():
        parts.append(f"{key}={value}")
    line = " ".join(parts)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()


def overlay_log_session() -> None:
    overlay_log("session", path=str(LOG_PATH))
