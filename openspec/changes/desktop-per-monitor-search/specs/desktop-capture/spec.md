## Purpose

Locate and OCR the MapleStory EXP bar via desktop BitBlt only: locked small-crop polling plus a multi-monitor search funnel that avoids binding the game HWND.

## ADDED Requirements

### Requirement: Locked monitoring uses small desktop crops only

While the locator is locked, the system MUST capture only the locked EXP-bar rectangle from the desktop composite (virtual-screen coordinates) on each monitor tick. The system MUST NOT create a Graphics Capture session for the game window and MUST NOT enumerate windows by MapleStory title for capture.

#### Scenario: Locked tick grabs crop only

- **WHEN** the locator is in the locked state and a monitor tick runs
- **THEN** the system captures only the locked rectangle via desktop region grab and runs label presence / OCR on that crop

#### Scenario: No game-window capture path

- **WHEN** capturing for locked monitoring or search
- **THEN** the system does not call window-bound Graphics Capture (`CreateForWindow`) and does not select a capture target by matching the game window title

### Requirement: Search uses a multi-monitor funnel

While searching or relocating, the system MUST search physical monitors individually (`monitors[1..n]`), not the virtual-desktop bounding box (`monitors[0]`). Search MUST follow this order and stop at the first label match: (1) if a last-known locked rectangle exists, a neighborhood around that rectangle; (2) for each physical monitor in preference order (last-hit monitor first, then others): match the bottom HUD band, and if that misses match the remaining upper portion of the same monitor before moving on. On a successful match the system MUST record the hit monitor index for the next search preference and store the locked OCR rectangle in virtual-screen coordinates.

#### Scenario: Relocate prefers neighborhood then last monitor

- **WHEN** the locator enters relocating with a last-known rectangle and last-hit monitor
- **THEN** the next search attempts the neighborhood of that rectangle before any monitor bands, and processes the last-hit monitor (bottom band, then upper remainder if needed) before other monitors

#### Scenario: Cold start finds label not in bottom band

- **WHEN** searching with no last-known rectangle and the EXP label lies only in the upper portion of a monitor
- **THEN** after that monitor’s bottom HUD band misses, the system searches that monitor’s remaining upper portion and can still lock the label

#### Scenario: Common case stops on bottom band

- **WHEN** searching and the EXP label lies in the bottom HUD band of the preferred monitor
- **THEN** the system locks after the bottom-band match and does not capture that monitor’s upper remainder

#### Scenario: Hit updates last-hit monitor

- **WHEN** a label match is found on a given physical monitor
- **THEN** that monitor becomes the preferred monitor for the next search
### Requirement: Search matches with monitor-appropriate template scale

When matching on a monitor (or a region on that monitor), the system MUST use template scale(s) appropriate to that monitor’s DPI scaling instead of blindly trying the full global scale list on every search region. Acceptance MUST still succeed for the setups in `docs/display.md` (screen 1 @ 1.5× with 1366×768 game window; screen 2 @ 1.0× with 1920×1080).

#### Scenario: Primary monitor uses 1.0-class scale

- **WHEN** searching the 1.0× primary monitor (screen 2 per display spec)
- **THEN** matching uses 1.0-appropriate scale(s) and can lock the EXP label for a 1920×1080 game window on that screen

#### Scenario: Secondary 1.5× monitor uses 1.5-class scale

- **WHEN** searching the 1.5× secondary monitor (screen 1 per display spec)
- **THEN** matching uses 1.5-appropriate scale(s) and can lock the EXP label for a 1366×768 game window on that screen

### Requirement: Hide own preview before every search capture

Before any search or relocate desktop capture, the system MUST hide the EXP crop preview image inside the tool window while keeping the preview area height and overall window layout unchanged. The system MUST flush pending UI painting for that hide before capturing. The system MUST NOT rely on excluding the tool window rectangle from the search bitmap as the primary anti-false-match mechanism.

#### Scenario: Preview hidden with stable height

- **WHEN** a search capture is about to run and a crop preview was visible
- **THEN** the preview image is hidden, the preview canvas height remains unchanged, and capture occurs only after the hide has been applied to the on-screen pixels

#### Scenario: Preview does not produce a false lock

- **WHEN** searching while the tool window is visible on a monitored screen
- **THEN** the system does not lock onto the tool’s own preview as the game EXP label

### Requirement: Capture reuse and non-goals for detection surface

The system SHOULD reuse a long-lived desktop capture session/handle across grabs within the process lifetime. The system MUST NOT introduce DXGI Desktop Duplication or GPU-accelerated template matching for this change.

#### Scenario: No DXGI or GPU matcher

- **WHEN** implementing desktop search and locked grabs for this change
- **THEN** capture remains GDI/mss-style desktop BitBlt (or equivalent existing stack) without DXGI Desktop Duplication and without GPU `matchTemplate`
