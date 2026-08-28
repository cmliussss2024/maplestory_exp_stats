# EXP History Sanitize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist `{t, exp}` only (`t` always 6 decimal places), and derive rates by sanitizing the raw series so OCR valleys are skipped and real level-ups accumulate.

**Architecture:** `sanitize_exp_series(points, now) -> SanitizedExp` is the only self-check. `RateTracker` stores raw `ExpPoint`s, appends jsonl on exp change (including drops), and refreshes gains from the sanitizer on every `tick` / `hourly_rates`.

**Tech Stack:** Python 3, unittest (`python -m unittest tests.test_rate_tracker -v`)

## Global Constraints

- This feature uses TDD: failing test first, watch it fail, then minimal production code.
- Spec: `docs/superpowers/specs/2026-08-28-exp-history-sanitize-design.md`
- Do not rewrite existing `data/exp_history.jsonl`.
- Do not commit unless the user asks.
- Do not change OCR, UI, or chart consumers.
- `LEVEL_CONFIRM_SECONDS` stays `10.0`.
- New jsonl lines: keys `t` then `exp` only; `t` serialized with `format(t, ".6f")`.

## File Structure

- Modify: `rate_tracker.py` — add `ExpPoint`, `SanitizedExp`, `sanitize_exp_series`; move `_is_inflated_baseline` / `_is_truncated_expansion` / `_plausible_gain` to module-level functions used by the sanitizer; `RateTracker` holds `_points`, persists `{t, exp}`, calls sanitizer.
- Modify: `tests/test_rate_tracker.py` — new sanitizer / persist tests; update `d` assertions and the confirmed level-up total (`5240`); replace `_last_exp` hack with a raw inflated-baseline series.

---

### Task 1: `sanitize_exp_series` OCR valleys

**Files:**
- Modify: `rate_tracker.py`
- Test: `tests/test_rate_tracker.py`

**Interfaces:**
- Consumes: nothing new
- Produces:
  - `ExpPoint(t: float, exp: int)`
  - `SanitizedExp(last_exp: int | None, gains: tuple[tuple[float, int], ...], first_gain_at: float | None, last_gain_at: float | None, last_gain: int)`
  - `sanitize_exp_series(points: Sequence[ExpPoint], now: float) -> SanitizedExp`

- [ ] **Step 1: Write the failing tests**

Add import `ExpPoint, sanitize_exp_series` and this class at the end of `tests/test_rate_tracker.py`:

```python
class SanitizeExpSeriesTests(unittest.TestCase):
    def test_single_ocr_valley_is_skipped(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 10001), ExpPoint(1.0, 1010), ExpPoint(2.0, 10204)],
            now=2.0,
        )
        self.assertEqual(result.last_exp, 10204)
        self.assertEqual(sum(delta for _t, delta in result.gains), 203)

    def test_repeated_ocr_valley_is_skipped(self):
        points = [ExpPoint(0.0, 10099)]
        points.extend(ExpPoint(float(i), 1010) for i in range(1, 6))
        points.append(ExpPoint(6.0, 10200))
        result = sanitize_exp_series(points, now=6.0)
        self.assertEqual(result.last_exp, 10200)
        self.assertEqual(sum(delta for _t, delta in result.gains), 101)

    def test_jittered_ocr_valley_is_skipped(self):
        result = sanitize_exp_series(
            [
                ExpPoint(0.0, 10099),
                ExpPoint(1.0, 1010),
                ExpPoint(2.0, 1015),
                ExpPoint(3.0, 1020),
                ExpPoint(4.0, 10200),
            ],
            now=4.0,
        )
        self.assertEqual(result.last_exp, 10200)
        self.assertEqual(sum(delta for _t, delta in result.gains), 101)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_rate_tracker.SanitizeExpSeriesTests -v`

Expected: FAIL / ERROR with `ExpPoint` or `sanitize_exp_series` not defined.

- [ ] **Step 3: Write minimal implementation**

In `rate_tracker.py`, add `Sequence` to the typing imports and these types plus `sanitize_exp_series` that:

1. Accepts the first point as baseline (no gain).
2. On equal exp, skips.
3. On rise: truncated-expansion → accept delta 0; else if plausible → accept `new - last`; else skip.
4. On drop: inflated-baseline → accept delta 0; else collect valley `V` until a recovery jump or end of list.
5. Recovery jump: `c.exp >= a.exp` and `plausible(a, c)` and not `plausible(v, c)` → skip `V`, accept `c` with `delta = c.exp - a.exp`.
6. No recovery and `now - V[0].t >= LEVEL_CONFIRM_SECONDS` → accept `V[0]` as new baseline (delta 0), continue from `V[1]`.
7. No recovery and duration `< 10` → skip `V`.

Lift `_is_inflated_baseline`, `_is_truncated_expansion`, `_plausible_gain` to module-level functions (same bodies) so the sanitizer and `RateTracker` share them. Keep thin staticmethod wrappers if existing tests call them on the class; otherwise call the module functions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_rate_tracker.SanitizeExpSeriesTests -v`

Expected: PASS

- [ ] **Step 5: Commit**

Skip unless the user asks.

---

### Task 2: Level-up, 10s gate, correction

**Files:**
- Modify: `rate_tracker.py` (sanitizer only if Task 1 left stubs)
- Test: `tests/test_rate_tracker.py`

**Interfaces:**
- Consumes: `sanitize_exp_series`, `ExpPoint`, `LEVEL_CONFIRM_SECONDS = 10.0`
- Produces: same `SanitizedExp` fields; confirmed level-up counts `V[0]` onward (`5240` case)

- [ ] **Step 1: Write the failing tests**

Append to `SanitizeExpSeriesTests`:

```python
    def test_confirmed_level_up_accumulates_both_sides(self):
        result = sanitize_exp_series(
            [
                ExpPoint(0.0, 90000),
                ExpPoint(1.0, 95000),
                ExpPoint(2.0, 120),
                ExpPoint(3.0, 200),
                ExpPoint(13.0, 280),
                ExpPoint(14.0, 360),
            ],
            now=14.0,
        )
        self.assertEqual(result.last_exp, 360)
        self.assertEqual(sum(delta for _t, delta in result.gains), 5240)

    def test_unconfirmed_valley_keeps_previous_baseline(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 10099), ExpPoint(1.0, 1010)],
            now=6.0,
        )
        self.assertEqual(result.last_exp, 10099)
        self.assertEqual(result.gains, ())

    def test_timeout_confirms_level_up(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 10099), ExpPoint(1.0, 1010)],
            now=16.0,
        )
        self.assertEqual(result.last_exp, 1010)
        self.assertEqual(result.gains, ())

    def test_recovery_after_timeout_reclassifies_as_ocr(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 10099), ExpPoint(1.0, 1010), ExpPoint(16.0, 10200)],
            now=16.0,
        )
        self.assertEqual(result.last_exp, 10200)
        self.assertEqual(sum(delta for _t, delta in result.gains), 101)

    def test_gradual_climb_after_level_up_is_not_ocr(self):
        points = [ExpPoint(0.0, 10099), ExpPoint(1.0, 50)]
        exp = 50
        for second in range(2, 122):
            exp += 100
            points.append(ExpPoint(float(second), exp))
        result = sanitize_exp_series(points, now=121.0)
        self.assertEqual(result.last_exp, exp)
        self.assertEqual(sum(delta for _t, delta in result.gains), exp - 50)
        self.assertNotEqual(sum(delta for _t, delta in result.gains), exp - 10099)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_rate_tracker.SanitizeExpSeriesTests -v`

Expected: new cases FAIL until level-up / timeout / climb logic is complete.

- [ ] **Step 3: Complete sanitizer branches** from Task 1 step 3 (timeout confirm, accept `V[0]` then continue, recovery after timeout via full-series rerun).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_rate_tracker.SanitizeExpSeriesTests -v`

Expected: PASS

- [ ] **Step 5: Commit**

Skip unless the user asks.

---

### Task 3: Preserve existing OCR behaviors via sanitizer

**Files:**
- Test: `tests/test_rate_tracker.py`
- Modify: `rate_tracker.py` if any retained heuristic is missing

**Interfaces:**
- Consumes: `sanitize_exp_series`
- Produces: same outcomes as current `OcrRecoveryTests` except confirmed level-up total `5240`

- [ ] **Step 1: Write failing sanitizer tests for retained cases**

```python
    def test_implausible_jump_is_skipped(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 8486), ExpPoint(1.0, 1_359_000)],
            now=1.0,
        )
        self.assertEqual(result.last_exp, 8486)
        self.assertEqual(result.gains, ())

    def test_truncated_drop_recovers(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 25852), ExpPoint(1.0, 2586), ExpPoint(2.0, 25863)],
            now=2.0,
        )
        self.assertEqual(result.last_exp, 25863)
        self.assertEqual(sum(delta for _t, delta in result.gains), 11)

    def test_truncated_expansion_resets_baseline(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 6685), ExpPoint(1.0, 67106)],
            now=1.0,
        )
        self.assertEqual(result.last_exp, 67106)
        self.assertEqual(result.gains, ())

    def test_suffix_noise_is_not_a_gain(self):
        result = sanitize_exp_series(
            [ExpPoint(0.0, 103546), ExpPoint(1.0, 1035461)],
            now=1.0,
        )
        self.assertEqual(result.last_exp, 103546)
        self.assertEqual(result.gains, ())

    def test_inflated_baseline_recovers(self):
        result = sanitize_exp_series(
            [
                ExpPoint(0.0, 1035461),
                ExpPoint(2.0, 107016),
                ExpPoint(3.0, 107062),
                ExpPoint(4.0, 107108),
            ],
            now=4.0,
        )
        self.assertEqual(result.last_exp, 107108)
        self.assertEqual(sum(delta for _t, delta in result.gains), 92)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_rate_tracker.SanitizeExpSeriesTests -v`

Expected: FAIL only on missing heuristics.

- [ ] **Step 3: Wire existing heuristic functions into the rise/drop branches** (already specified in Task 1).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_rate_tracker.SanitizeExpSeriesTests -v`

Expected: PASS

- [ ] **Step 5: Commit**

Skip unless the user asks.

---

### Task 4: `RateTracker` uses sanitizer; persist `{t, exp}` with 6-dp `t`

**Files:**
- Modify: `rate_tracker.py` (`RateTracker.__init__`, `_record`, `_append_history`, `_load_history`, `clear`, `tick`, `hourly_rates`)
- Test: `tests/test_rate_tracker.py`

**Interfaces:**
- Consumes: `sanitize_exp_series`, `ExpPoint`, `SanitizedExp`
- Produces:
  - `_points: list[ExpPoint]` raw history
  - `_refresh(now)` applies sanitizer into `_last_exp` / `_gains` / gain timestamps
  - `_append_history(now, exp)` writes `{"t": 1787839419.038550, "exp": 275742}\n` with no `d`
  - Load ignores extra keys including `d`

- [ ] **Step 1: Write the failing persist / tracker tests**

Update `HistoryPersistTests.test_reloads_gains_from_disk` to assert `"d" not in last` and the `t` text has exactly 6 fractional digits.

Add:

```python
    def test_timestamp_is_serialized_with_six_decimals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            tracker = RateTracker(history_path=path)
            tracker.tick(1000, now=1787839419.03855)
            line = path.read_text(encoding="utf-8").strip()
            self.assertEqual(line, '{"t": 1787839419.038550, "exp": 1000}')

    def test_drop_is_persisted_and_skipped_on_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            first = RateTracker(history_path=path)
            first.tick(10001, now=1.0)
            first.tick(1010, now=2.0)
            first.tick(10204, now=3.0)
            text = path.read_text(encoding="utf-8")
            self.assertIn('"exp": 1010', text)
            second = RateTracker(history_path=path)
            self.assertEqual(second.last_exp, 10204)
            self.assertEqual(second.total_gained(), 203)

    def test_legacy_records_with_d_still_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exp_history.jsonl"
            path.write_text(
                '{"t": 1787766181.7113051, "exp": 1000, "d": 0}\n'
                '{"t": 1787766182.1234567, "exp": 1100, "d": 100}\n',
                encoding="utf-8",
            )
            tracker = RateTracker(history_path=path)
            self.assertEqual(tracker.last_exp, 1100)
            self.assertEqual(tracker.total_gained(), 100)
```

Change `OcrRecoveryTests.test_confirmed_level_up_keeps_the_new_baseline` expected total from `5080` to `5240` and `per_hour` to `int(round(5240 * 3600 / 13))`.

Replace `test_recovers_from_inflated_baseline_and_counts_gains_again` so it does not assign `tracker._last_exp`; start from `1035461` then `107016` / `107062` / `107108`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_rate_tracker.HistoryPersistTests tests.test_rate_tracker.OcrRecoveryTests -v`

Expected: persist tests FAIL on `d` still present / `t` not 6dp / drop not written; level-up total still `5080`.

- [ ] **Step 3: Write minimal RateTracker wiring**

- `_points: list[ExpPoint]`; drop `_pre_level_exp` / `_level_suspect_at`.
- `_round_t(now) -> float`: `float(format(now, ".6f"))`.
- `_record`: ignore `None`; if exp changed vs last raw point, append `ExpPoint` and persist; `_refresh(now)`.
- `_refresh(now)`: `result = sanitize_exp_series(self._points, now)` then copy fields into `_last_exp`, `_gains`, `_first_gain_at`, `_last_gain_at`, `_last_gain`.
- `tick` and `hourly_rates` call `_refresh(now)` so an open valley can confirm after reload using wall-clock `now`.
- `_append_history`: mkdir, write `'{"t": %s, "exp": %d}\n' % (format(t, ".6f"), exp)` with `t = _round_t(now)`.
- `_load_history`: parse lines, skip bad JSON, `ExpPoint(float(item["t"]), int(item["exp"]))`; ignore other keys; `_refresh` with last point `t` if any.
- `clear`: clear `_points` and the rest; truncate file.

- [ ] **Step 4: Run the full tracker tests**

Run: `python -m unittest tests.test_rate_tracker -v`

Expected: all PASS.

- [ ] **Step 5: Commit**

Skip unless the user asks.

---

## Spec coverage

| Spec requirement | Task |
|---|---|
| No `d`; compute after sanitize | 4 |
| Skip valleys at compute; do not rewrite jsonl | 1, 4 |
| `10001, 1010, 10204` and `1010×N` | 1 |
| Level-up accumulates both sides (`5240`) | 2, 4 |
| 10s confirm then recovery corrects | 2 |
| `t` always 6 decimal places | 4 |
| Persist drops; load old `d` rows | 4 |
| Retained OCR heuristics | 3 |
| TDD | every task |
