## 1. Docs sync

- [x] 1.1 Rewrite `docs/desktop-capture-evaluation.md` search path to the funnel (per-monitor band→remainder, neighborhood, last-hit preference, preview hide, DPI shortlist, mss reuse; no `monitors[0]` / no self-window mask) and verify the doc matches `openspec/changes/desktop-per-monitor-search/specs/desktop-capture/spec.md`
- [x] 1.2 Update `docs/todos/desktop-capture.md` checkboxes to the same funnel items and verify they cite the updated evaluation doc

## 2. Capture primitives

- [x] 2.1 Add a long-lived shared `mss` instance for region/monitor grabs in `vision.py` and verify locked/search grabs no longer construct a new `mss.mss()` per call
- [x] 2.2 Make `grab_region` mss-region-only (remove `_grab_from_game_window` from the hot path) and verify a locked tick never calls `CreateForWindow` / `grab_hwnd`
- [x] 2.3 Add `find_label` scale shortlist by monitor DPI (1.0-class vs 1.5-class per design) and verify existing `tests/test_vision.py` still passes for fixture scales

## 3. Locator memory

- [x] 3.1 Add `last_rect` and `last_monitor_index` on `Locator`, preserve them across `RELOCATING`, clear on `FAILED`/`retry`, update on successful lock, and verify `tests/test_locator.py` covers relocate-preserves-last and retry-clears

## 4. Search funnel

- [x] 4.1 Replace `capture_for_search` with a funnel API: neighborhood (~300px) → for each monitor (last-hit first): bottom 30% band then upper 70% remainder; never use `monitors[0]`; stop on first hit; return virtual OCR rect + monitor index — verify unit tests cover band-hit (no remainder grab) and upper-only hit (band miss then remainder hit)
- [x] 4.2 Wire `app.py` search/relocate ticks to hide preview (`set_preview_visible(False)`, height unchanged), `update_idletasks`, then call the funnel and feed `locator.on_search_result` — verify search does not run while preview pixels still show the crop
- [x] 4.3 Update `scripts/crop_exp_assets.py` off hwnd `capture_for_search` onto desktop/monitor grab and verify the script still writes the three asset files

## 5. Remove game HWND capture

- [x] 5.1 Remove runtime `CreateForWindow` / title-based `find_game_window` capture usage from the app path (delete or quarantine dead code in `window_capture.py` / `vision.py` as needed) and verify no import/call remains on the monitor tick path
- [x] 5.2 Run `python -m unittest tests.test_vision tests.test_locator` (and any new funnel tests) and verify all pass

## 6. Manual acceptance

- [x] 6.1 Manually lock EXP on screen 2 (1920×1080 @ 1.0×) and screen 1 (1366×768 @ 1.5×) per `docs/display.md`, confirm relocate prefers last monitor / neighborhood, and verify the tool preview is not matched as the game label
