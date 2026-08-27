"""Turn OCR text from the MapleStory EXP bar into an integer."""

from __future__ import annotations

import re

_CONFUSABLES = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "|": "1",
    }
)

_EXP_PREFIX = re.compile(r"(?:EXP|XP|EP)(?![A-Z])", re.IGNORECASE)
_BEFORE_BRACKET = re.compile(r"^\s*([\d\s]+)\s*\[")
_TRAILING_PERCENT = re.compile(r"(\d{1,2}[.\-]\d{1,3})\D*$")
_HP_ONLY = re.compile(r"\bHP\b", re.IGNORECASE)


def parse_exp(text: str) -> int | None:
    if not text:
        return None
    raw = text.replace("岁", "%").translate(_CONFUSABLES)
    if _HP_ONLY.search(raw) and not _EXP_PREFIX.search(raw):
        return None
    match = _EXP_PREFIX.search(raw)
    if not match:
        return None
    return _digits_before_percent(raw[match.end() :])


def pick_exp(readings: list[tuple[str, float]]) -> int | None:
    best: tuple[int, float, bool] | None = None
    for text, conf in readings:
        value = parse_exp(text)
        if value is None:
            continue
        well_formed = "[" in (text or "")
        if (
            best is None
            or (well_formed and not best[2])
            or (well_formed == best[2] and conf > best[1])
        ):
            best = (value, conf, well_formed)
    return None if best is None else best[0]


def _digits_before_percent(rest: str) -> int | None:
    bracket = _BEFORE_BRACKET.search(rest)
    if bracket:
        return _to_int(bracket.group(1))
    percent = _TRAILING_PERCENT.search(rest)
    head = rest[: percent.start()] if percent else rest
    return _to_int(head)


def _to_int(chunk: str) -> int | None:
    digits = re.sub(r"\D", "", chunk)
    if not digits or len(digits) > 12:
        return None
    return int(digits)
