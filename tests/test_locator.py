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

    def test_three_search_misses_fail(self):
        loc = Locator()
        loc.on_search_result(None)
        loc.on_search_result(None)
        loc.on_search_result(None)
        self.assertEqual(loc.state, LocatorState.FAILED)

    def test_three_locked_misses_start_relocating(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40))
        loc.on_lock_check(False)
        loc.on_lock_check(False)
        loc.on_lock_check(False)
        self.assertEqual(loc.state, LocatorState.RELOCATING)
        self.assertIsNone(loc.locked_rect)

    def test_ocr_miss_does_not_count_as_lock_miss(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40))
        loc.on_lock_check(True)
        loc.on_lock_check(True)
        self.assertEqual(loc.state, LocatorState.LOCKED)

    def test_relocate_three_misses_fail(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40))
        loc.on_lock_check(False)
        loc.on_lock_check(False)
        loc.on_lock_check(False)
        loc.on_search_result(None)
        loc.on_search_result(None)
        loc.on_search_result(None)
        self.assertEqual(loc.state, LocatorState.FAILED)

    def test_relocate_success_locks_new_rect(self):
        loc = Locator()
        loc.on_search_result((10, 20, 200, 40))
        loc.on_lock_check(False)
        loc.on_lock_check(False)
        loc.on_lock_check(False)
        loc.on_search_result((30, 40, 200, 40))
        self.assertEqual(loc.state, LocatorState.LOCKED)
        self.assertEqual(loc.locked_rect, (30, 40, 200, 40))

    def test_retry_from_failed_starts_searching(self):
        loc = Locator()
        loc.on_search_result(None)
        loc.on_search_result(None)
        loc.on_search_result(None)
        loc.retry()
        self.assertEqual(loc.state, LocatorState.SEARCHING)
        self.assertIsNone(loc.locked_rect)
