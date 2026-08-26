"""Turn OCR text from the MapleStory EXP bar into an integer."""

from __future__ import annotations

import re

_EXP_RE = re.compile(r"EXP\s*(\d+)\s*\[", re.IGNORECASE)


def parse_exp(text: str) -> int | None:
    match = _EXP_RE.search(text or "")
    if not match:
        return None
    return int(match.group(1))
