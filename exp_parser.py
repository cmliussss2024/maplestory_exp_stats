"""Turn OCR text from the MapleStory EXP bar into an integer."""

from __future__ import annotations

import re
from dataclasses import dataclass

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
_OPEN_BRACKET = r"[\[［【]"
_CLOSE_BRACKET = r"[\]］】]"
_BEFORE_BRACKET = re.compile(rf"^\s*([\d\s]+)\s*{_OPEN_BRACKET}")
_TRAILING_PERCENT = re.compile(r"(\d{1,2}[.\-]\d{1,3})\D*$")
_BRACKET_INNER = re.compile(rf"{_OPEN_BRACKET}([^\[\]［］【】]*){_CLOSE_BRACKET}")
# '[' / ']' often become '1'; '.' is dropped: "106034186381" is 106034 + [86.38]
_GLUED_CLOSED_PERCENT = re.compile(r"^(\d+?)1(\d{1,2})(\d{2,3})1$")
_GLUED_OPEN_PERCENT = re.compile(r"^(\d+?)1(\d{1,2})(\d{2,3})$")
_LEFTOVER_OPEN_BRACKET = re.compile(r"[\[［【1]\s*$")
_PERCENT_VALUE = re.compile(r"(100(?:\.0{1,3})?|\d{1,2}\.\d{1,3})")
_HP_ONLY = re.compile(r"\bHP\b", re.IGNORECASE)


@dataclass(frozen=True)
class ExpReading:
    exp: int
    percent: float | None


def parse_exp(text: str) -> int | None:
    reading = parse_exp_reading(text)
    return None if reading is None else reading.exp


def parse_exp_reading(text: str) -> ExpReading | None:
    if not text:
        return None
    raw = text.replace("岁", "%").translate(_CONFUSABLES)
    if _HP_ONLY.search(raw) and not _EXP_PREFIX.search(raw):
        return None
    match = _EXP_PREFIX.search(raw)
    if not match:
        return None
    rest = raw[match.end() :]
    exp = _digits_before_percent(rest)
    if exp is None:
        return None
    return ExpReading(exp, _parse_percent(rest))


def pick_exp(readings: list[tuple[str, float]]) -> int | None:
    reading = pick_exp_reading(readings)
    return None if reading is None else reading.exp


def pick_exp_reading(readings: list[tuple[str, float]]) -> ExpReading | None:
    best: tuple[ExpReading, float, bool] | None = None
    for text, conf in readings:
        value = parse_exp_reading(text)
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
    if percent:
        head = _LEFTOVER_OPEN_BRACKET.sub("", rest[: percent.start()])
        return _to_int(head)
    glued = _glued_percent_match(rest)
    if glued is not None:
        return glued[0]
    return _to_int(rest)


def _glued_percent_match(rest: str) -> tuple[int, float] | None:
    digits = re.sub(r"\D", "", rest)
    for pattern in (_GLUED_CLOSED_PERCENT, _GLUED_OPEN_PERCENT):
        glued = pattern.fullmatch(digits)
        if glued is None:
            continue
        percent = _percent_from_chunk(f"{glued.group(2)}.{glued.group(3)}")
        if percent is not None:
            return int(glued.group(1)), percent
    return None


def _to_int(chunk: str) -> int | None:
    digits = re.sub(r"\D", "", chunk)
    if not digits or len(digits) > 12:
        return None
    return int(digits)


def _parse_percent(rest: str) -> float | None:
    bracket = _BRACKET_INNER.search(rest)
    if bracket:
        return _percent_from_chunk(bracket.group(1))
    match = _TRAILING_PERCENT.search(rest)
    if match:
        return _percent_from_chunk(match.group(1))
    glued = _glued_percent_match(rest)
    if glued is not None:
        return glued[1]
    return None


def _percent_from_chunk(chunk: str) -> float | None:
    match = _PERCENT_VALUE.search(chunk.replace("-", "."))
    if not match:
        return None
    value = float(match.group(1))
    if value < 0 or value > 100:
        return None
    return value
