from __future__ import annotations

from enum import Enum


class LocatorState(Enum):
    SEARCHING = "searching"
    LOCKED = "locked"
    RELOCATING = "relocating"
    FAILED = "failed"


class Locator:
    SEARCH_FAIL_LIMIT = 20
    LOCK_FAIL_LIMIT = 3
    SEARCH_INTERVAL_SECONDS = 3

    def __init__(self) -> None:
        self.state = LocatorState.SEARCHING
        self.locked_rect: tuple[int, int, int, int] | None = None
        self._search_misses = 0
        self._lock_misses = 0

    @property
    def search_misses(self) -> int:
        return self._search_misses

    def on_search_result(self, rect: tuple[int, int, int, int] | None) -> None:
        if self.state not in (LocatorState.SEARCHING, LocatorState.RELOCATING):
            return
        if rect is not None:
            self.locked_rect = rect
            self.state = LocatorState.LOCKED
            self._search_misses = 0
            self._lock_misses = 0
            return
        self._search_misses += 1
        if self._search_misses > self.SEARCH_FAIL_LIMIT:
            self.state = LocatorState.FAILED
            self.locked_rect = None

    def on_lock_check(self, found: bool) -> None:
        if self.state != LocatorState.LOCKED:
            return
        if found:
            self._lock_misses = 0
            return
        self._lock_misses += 1
        if self._lock_misses >= self.LOCK_FAIL_LIMIT:
            self.state = LocatorState.RELOCATING
            self.locked_rect = None
            self._search_misses = 0
            self._lock_misses = 0

    def retry(self) -> None:
        self.state = LocatorState.SEARCHING
        self.locked_rect = None
        self._search_misses = 0
        self._lock_misses = 0
