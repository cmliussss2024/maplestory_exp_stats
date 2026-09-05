## Context

See `proposal.md` for motivation. Today `grab_region` prefers `_grab_from_game_window` (WGC / hwnd), and `capture_for_search` grabs the game window or falls back to `mss.monitors[0]`. `find_label` tries a long `_LABEL_SCALES` list. `Locator.on_lock_check` clears `locked_rect` when entering `RELOCATING`, which would block neighborhood search unless last-hit geometry is preserved separately. Preview already has `set_preview_visible`, but search must guarantee hide + paint flush before grab. Display/DPI constraints live in `docs/display.md`.

## Goals / Non-Goals

**Goals:**

- Ship the desktop-only capture path with the full search funnel (preview hide → neighborhood → per monitor bottom band then upper remainder, last-hit first).
- Preserve locator fail limits / 3s search interval / 1s lock tick semantics.
- Keep detection surface light (no game HWND capture, no DXGI/GPU matcher).
- Update evaluation + todo docs to match.

**Non-Goals:**

- Changing HUD chrome, overlay, OCR parser, or charts.
- Parallel multi-monitor matching.
- Persisting last-hit monitor across process restarts (in-session only).
- Guaranteeing exclusive-fullscreen / non-DWM readability.

## Decisions

### 1. Per-monitor grabs, never `monitors[0]` for search

- **Choice:** Iterate `sct.monitors[1:]` for band search; neighborhood uses an explicit virtual-screen rect via region grab.
- **Why:** Avoids virtual bounding-box dead pixels when heights differ; enables early exit.
- **Alternatives:** Single `monitors[0]` grab (simpler, worse cost on multi-mon / uneven layouts).

### 2. Preserve last geometry when leaving LOCKED

- **Choice:** Keep `last_rect` (virtual OCR/lock rect) and `last_monitor_index` across `RELOCATING`; clear on `FAILED` / `retry` / successful new lock updates them. Do not depend on current `locked_rect` alone if state machine still nulls it for “unlocked” semantics—store dedicated fields.
- **Why:** Neighborhood + monitor preference need memory; today’s `locked_rect = None` on relocate would erase it.
- **Alternatives:** Infer monitor only from last rect center each time (still need the rect).

### 3. Neighborhood, then per-monitor band-with-remainder

- **Choice:** Neighborhood pad ≈ 300px (clamp to virtual desktop). For each monitor (last-hit first): try bottom 30% HUD band; on miss, try the remaining upper 70% of that same monitor before the next monitor. Never use `monitors[0]`. Stop at first hit.
- **Why:** Maximized / bottom-docked games pay only the band cost; windowed games in the upper half still cold-start without guessing layout. Same-monitor remainder beats “all bands then all full screens” because a hit on screen A’s upper half does not wait for B/C band misses.
- **Alternatives:** Band-only (fails upper-half windows); always full monitor (simpler, slower common case); all bands then all fulls (worse latency when label is upper on early monitor).

### 4. DPI → scale shortlist per monitor

- **Choice:** Map monitor DPI scale (from Win32 monitor DPI at monitor center, or mss geometry + `docs/display.md` knowledge) to a small scale shortlist (e.g. 1.0× → `{1.0, 1.1}`; 1.5× → `{1.5, 1.35, 1.6}`), not the full `_LABEL_SCALES` tour.
- **Why:** Wrong scales dominate `matchTemplate` cost; acceptance setups are known.
- **Alternatives:** Keep full scale list (safe but slow); single exact DPI scale only (brittle if user changes game resolution).

### 5. Preview hide before capture

- **Choice:** On search/relocate path: `set_preview_visible(False)` (or clear image pixels), keep canvas height; `update_idletasks()`; avoid full `update()` unless paint still stale. Then run funnel.
- **Why:** Spec requires no false lock on own preview; height stability avoids layout jump.
- **Alternatives:** Subtract tool HWND from bitmap (extra geometry, still fails if preview was the only issue and other UI lacks EXP glyphs).

### 6. Long-lived `mss` instance

- **Choice:** Module-level or app-owned `mss.mss()` reused for region and monitor grabs; create on first use, close on shutdown if practical.
- **Why:** Drops per-call setup cost on 1Hz lock + 3s search.
- **Alternatives:** `with mss.mss()` every call (current pattern).

### 7. Remove WGC game path in same change

- **Choice:** `grab_region` → mss region only; delete/stop `CreateForWindow` usage and title-based `find_game_window` for runtime capture (crop script may need a documented desktop/manual path later).
- **Why:** Core detection-surface goal of the evaluation.
- **Alternatives:** Keep WGC as fallback (keeps fingerprint).

### 8. Docs sync

- **Choice:** Rewrite search sections in `docs/desktop-capture-evaluation.md` and checkboxes in `docs/todos/desktop-capture.md` to describe the funnel (not “整张虚拟桌面” / “排除自身窗口矩形”).

## Risks / Trade-offs

- [Bottom 30% misses EXP if window is upper-half] → Mitigation: same-monitor upper remainder immediately after band miss (required in funnel).
- [Neighborhood uses stale rect after drag to another monitor] → Mitigation: neighborhood miss falls through to last-monitor band then all monitors.
- [Hide preview race with compositor] → Mitigation: idletasks + verify; if flaky, one short `after` idle before grab (keep height).
- [Crop script depended on `capture_for_search` hwnd] → Mitigation: point script at desktop funnel or explicit monitor grab; document in tasks.
- [Clearing `locked_rect` on relocate breaks callers] → Mitigation: dedicated `last_rect` / API so UI “unlocked” stays correct while search remembers geometry.

## Migration Plan

1. Implement mss-only `grab_region` + shared sct.
2. Locator last-hit fields + search funnel + preview-hide hook in app tick.
3. Remove WGC / title find from runtime path.
4. Update evaluation/todo docs; run vision/locator tests and manual dual-monitor check per `docs/display.md`.
5. Rollback: revert change branch; no on-disk schema migration.

## Open Questions

- Neighborhood pad (default 300px) and bottom-band fraction (default 30%) may be tuned after manual dual-monitor trial without changing funnel order (neighborhood → per monitor band → same-monitor remainder → next monitor).
