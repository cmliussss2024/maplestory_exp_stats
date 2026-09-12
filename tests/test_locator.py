import unittest

from locator import Locator, LocatorState


class LocatorTests(unittest.TestCase):
    def test_starts_searching(self):
        loc = Locator()
        self.assertEqual(loc.state, LocatorState.SEARCHING)
        self.assertIsNone(loc.locked_rect)

    def test_first_match_locks_and_goes_reading(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40))
        self.assertEqual(loc.state, LocatorState.LOCKED)
        self.assertEqual(loc.locked_rect, (10, 20, 200, 40))

    def test_search_misses_fail_after_limit(self):
        loc = Locator()
        for _ in range(1 + Locator.SEARCH_FAIL_LIMIT):
            loc.on_search_result(None)
        self.assertEqual(loc.state, LocatorState.FAILED)

    def test_lock_misses_start_relocating_after_limit(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40), monitor_index=2)
        for _ in range(Locator.LOCK_FAIL_LIMIT - 1):
            loc.on_lock_check(False)
        self.assertEqual(loc.state, LocatorState.LOCKED)
        loc.on_lock_check(False)
        self.assertEqual(loc.state, LocatorState.RELOCATING)
        self.assertIsNone(loc.locked_rect)
        self.assertEqual(loc.last_rect, (10, 20, 200, 40))
        self.assertEqual(loc.last_monitor_index, 2)

    def test_retry_clears_last_hit(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40), monitor_index=1)
        for _ in range(Locator.LOCK_FAIL_LIMIT):
            loc.on_lock_check(False)
        loc.retry()
        self.assertEqual(loc.state, LocatorState.SEARCHING)
        self.assertIsNone(loc.locked_rect)
        self.assertIsNone(loc.last_rect)
        self.assertIsNone(loc.last_monitor_index)

    def test_failed_search_clears_last_hit(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40), monitor_index=1)
        for _ in range(Locator.LOCK_FAIL_LIMIT):
            loc.on_lock_check(False)
        for _ in range(1 + Locator.SEARCH_FAIL_LIMIT):
            loc.on_search_result(None)
        self.assertEqual(loc.state, LocatorState.FAILED)
        self.assertIsNone(loc.last_rect)
        self.assertIsNone(loc.last_monitor_index)

    def test_ocr_miss_does_not_count_as_lock_miss(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40))
        loc.on_lock_check(True)
        loc.on_lock_check(True)
        self.assertEqual(loc.state, LocatorState.LOCKED)

    def test_relocate_misses_fail_after_limit(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40))
        for _ in range(Locator.LOCK_FAIL_LIMIT):
            loc.on_lock_check(False)
        for _ in range(1 + Locator.SEARCH_FAIL_LIMIT):
            loc.on_search_result(None)
        self.assertEqual(loc.state, LocatorState.FAILED)

    def test_relocate_success_locks_new_rect(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40))
        for _ in range(Locator.LOCK_FAIL_LIMIT):
            loc.on_lock_check(False)
        loc.on_search_result((30, 40, 200, 40))
        self.assertEqual(loc.state, LocatorState.LOCKED)
        self.assertEqual(loc.locked_rect, (30, 40, 200, 40))

    def test_retry_from_failed_starts_searching(self):
        loc = Locator()
        for _ in range(1 + Locator.SEARCH_FAIL_LIMIT):
            loc.on_search_result(None)
        loc.retry()
        self.assertEqual(loc.state, LocatorState.SEARCHING)
        self.assertIsNone(loc.locked_rect)
