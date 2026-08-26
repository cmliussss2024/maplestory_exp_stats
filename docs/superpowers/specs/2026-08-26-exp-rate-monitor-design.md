# MapleStory EXP Rate Monitor — Design

Date: 2026-08-26

## Goal

A Windows desktop window that, once per second, reads MapleStory’s current EXP integer from the on-screen EXP bar and shows gain rates:

- per second (zero after 15s with no gain)
- per minute (zero after 60s with no gain)
- per hour (zero after 5 minutes with no gain)

## Non-goals

- Reading process memory
- Always-on-top overlay
- Tracking the percentage `[87.07%]`

## Stack

Python, `mss` screenshot, OpenCV template match, Tesseract or Windows OCR for digits, tkinter window (not topmost).

## Locate then lock

The EXP bar is a fixed HUD block (user-supplied crop: `EXP <integer>[percent%]` over a green bar).

1. On start (and on Retry), screenshot the full desktop and template-match a **stable** piece of that crop — the `EXP` label — not the changing digits.
2. First hit locks a screen rectangle: the label match plus a region to its right large enough for the number and percent.
3. Later ticks crop **only that locked rectangle**. No full-screen search.

Matching the full original screenshot as a template would fail as soon as the EXP digits change, so the runtime template is the left-hand `EXP` label extracted from the user’s image.

## Retry

“Miss” means the locked crop no longer contains the EXP label (covered, minimized, wrong map UI). An OCR miss with the label still visible does **not** count.

1. Locked position misses 3 consecutive seconds → full-screen search, up to 3 attempts (1/s).
2. Those 3 full-screen attempts also miss → stop. Window shows `读取失败` and enables **重试**.
3. 重试 resets counters and starts a new full-screen search.

## Parse

From the locked crop, OCR text like `EXP 256163[87.07%]`. Take the integer after `EXP` and before `[`. Ignore the percent. If OCR fails, skip the tick (no rate update, no locate-miss).

Level-up (new EXP < last EXP): update the baseline to the new value, do not record a negative gain.

## Rates

Keep a time series of positive per-tick gains.

- **每秒**: gain on the latest successful tick; `0` if no positive gain for 15s.
- **每分钟**: sum of gains in the last 60s; `0` if no positive gain for 60s.
- **每小时**: (sum of gains in the last 60s) × 60; `0` if no positive gain for 5 minutes.

## UI

Normal tkinter window, not always-on-top:

- Current EXP
- 每秒 / 每分钟 / 每小时
- Status: 定位中 / 读取中 / 重新定位 / 读取失败
- 重试 button, enabled only in 读取失败
