"""Screen capture, EXP-label matching, and OCR."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

from exp_parser import pick_exp

ASSETS = Path(__file__).resolve().parent / "assets"
LABEL_PATH = ASSETS / "exp_label.png"

# Locked crop relative to the EXP label: tight around text + yellow-green slot.
LABEL_IN_BAR = (1, 2)
MATCH_THRESHOLD = 0.78
OCR_WIDTH = 121
OCR_HEIGHT = 34
TEXT_ROW_HEIGHT = 16
OCR_UPSCALE = 3
# Cover 100%/125%/150%/200% DPI and fullscreen stretch of the game UI.
_LABEL_SCALES = (
    1.0, 1.25, 1.5, 1.75, 2.0, 0.75, 2.25, 2.5, 1.1, 1.35, 1.6, 1.85, 0.5, 3.0,
)

_ocr: RapidOCR | None = None
_label_bgr: np.ndarray | None = None
_desktop_origin = (0, 0)
_game_hwnd: int | None = None
_last_game_hwnd: int | None = None


def _load_label() -> np.ndarray:
    global _label_bgr
    if _label_bgr is None:
        image = cv2.imread(str(LABEL_PATH))
        if image is None:
            raise FileNotFoundError(f"Missing template: {LABEL_PATH}")
        _label_bgr = image
    return _label_bgr


def get_ocr() -> RapidOCR:
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR(use_text_det=False, use_angle_cls=False)
    return _ocr


def warmup() -> None:
    get_ocr()
    _load_label()


def find_label(screen_bgr: np.ndarray) -> tuple[tuple[int, int, int, int] | None, float]:
    templ = _load_label()
    screen_g = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    templ_g = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    th0, tw0 = templ_g.shape
    best_val = -1.0
    best_rect: tuple[int, int, int, int] | None = None
    for scale in _LABEL_SCALES:
        tw = max(8, int(round(tw0 * scale)))
        th = max(6, int(round(th0 * scale)))
        if th > screen_g.shape[0] or tw > screen_g.shape[1]:
            continue
        if scale == 1.0:
            scaled = templ_g
        else:
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            scaled = cv2.resize(templ_g, (tw, th), interpolation=interp)
        result = cv2.matchTemplate(screen_g, scaled, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val > best_val:
            best_val = float(max_val)
            sh, sw = scaled.shape
            best_rect = (int(max_loc[0]), int(max_loc[1]), int(sw), int(sh))
            if scale == 1.0 and max_val >= 0.95:
                break
    if best_rect is None or best_val < MATCH_THRESHOLD:
        return None, max(0.0, best_val)
    return best_rect, best_val


def label_rect_to_ocr_rect(
    label_rect: tuple[int, int, int, int],
    screen_w: int,
    screen_h: int,
) -> tuple[int, int, int, int]:
    x, y, w, _h = label_rect
    templ = _load_label()
    scale = w / templ.shape[1]
    ox = max(0, int(round(x - LABEL_IN_BAR[0] * scale)))
    oy = max(0, int(round(y - LABEL_IN_BAR[1] * scale)))
    width = min(int(round(OCR_WIDTH * scale)), screen_w - ox)
    height = min(int(round(OCR_HEIGHT * scale)), screen_h - oy)
    return (ox, oy, max(1, width), max(1, height))


def to_virtual_rect(
    screenshot_rect: tuple[int, int, int, int],
    origin: tuple[int, int],
) -> tuple[int, int, int, int]:
    x, y, w, h = screenshot_rect
    ox, oy = origin
    return (ox + x, oy + y, w, h)


def crop_bgr(screen_bgr: np.ndarray, rect: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = rect
    return screen_bgr[y : y + h, x : x + w]


def label_present(crop: np.ndarray) -> bool:
    rect, score = find_label(crop)
    return rect is not None and score >= MATCH_THRESHOLD


def read_exp_from_bgr(image_bgr: np.ndarray) -> int | None:
    if image_bgr.size == 0:
        return None
    readings: list[tuple[str, float]] = []
    for view in _ocr_views(image_bgr):
        text, conf = _ocr_text(view)
        if text:
            readings.append((text, conf))
    return pick_exp(readings)


def _text_row(image_bgr: np.ndarray) -> np.ndarray:
    height = image_bgr.shape[0]
    if height <= OCR_HEIGHT + 8:
        row_h = min(TEXT_ROW_HEIGHT, height)
    else:
        row_h = max(1, int(round(TEXT_ROW_HEIGHT * height / OCR_HEIGHT)))
    if height > row_h:
        return image_bgr[:row_h]
    return image_bgr


def _ocr_views(image_bgr: np.ndarray) -> list[np.ndarray]:
    row = _text_row(image_bgr)
    height, width = row.shape[:2]
    scaled = cv2.resize(
        row,
        (max(1, width * OCR_UPSCALE), max(1, height * OCR_UPSCALE)),
        interpolation=cv2.INTER_NEAREST,
    )
    return [row, scaled]


def _ocr_text(image_bgr: np.ndarray) -> tuple[str | None, float]:
    result, _elapse = get_ocr()(image_bgr)
    if not result:
        return None, 0.0
    text = " ".join(item[1] for item in result)
    conf = float(result[0][2]) if len(result[0]) > 2 else 0.0
    return text, conf


def grab_region(left: int, top: int, width: int, height: int) -> np.ndarray:
    image = _grab_from_game_window(left, top, width, height)
    if image is not None:
        return image
    return _grab_mss_region(left, top, width, height)


def _grab_mss_region(left: int, top: int, width: int, height: int) -> np.ndarray:
    from dpi import physical_call

    return physical_call(_mss_grab_impl, left, top, width, height)


def _mss_grab_impl(left: int, top: int, width: int, height: int) -> np.ndarray:
    import mss

    sct = mss.mss()
    frame = np.array(
        sct.grab({"left": left, "top": top, "width": max(1, width), "height": max(1, height)})
    )
    return frame[:, :, :3]


def _grab_from_game_window(left: int, top: int, width: int, height: int) -> np.ndarray | None:
    hwnd = _game_hwnd
    if hwnd is None:
        return None
    from window_capture import client_origin, grab_hwnd

    frame = grab_hwnd(hwnd)
    if frame is None:
        return None
    origin_x, origin_y = client_origin(hwnd)
    x = int(left - origin_x)
    y = int(top - origin_y)
    h, w = frame.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(w, x + max(1, width))
    y1 = min(h, y + max(1, height))
    if x1 <= x0 or y1 <= y0:
        return None
    return frame[y0:y1, x0:x1]


def grab_desktop() -> np.ndarray:
    from dpi import physical_call

    return physical_call(_grab_desktop_impl)


def _grab_desktop_impl() -> np.ndarray:
    import mss

    sct = mss.mss()
    monitor = sct.monitors[0]
    global _desktop_origin
    _desktop_origin = (int(monitor["left"]), int(monitor["top"]))
    frame = np.array(sct.grab(monitor))
    return frame[:, :, :3]


def find_game_window() -> tuple[int, int, int, int, str] | None:
    """Return (left, top, right, bottom, title) in virtual-screen coordinates."""
    global _game_hwnd, _last_game_hwnd
    import ctypes
    from ctypes import wintypes

    from dpi import logical_to_physical

    user32 = ctypes.windll.user32
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found: list[tuple[int, int, int, int, int, str]] = []

    def _enum(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        lowered = title.lower()
        if "冒险岛" not in title and "maplestory" not in lowered:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        left, top = logical_to_physical(hwnd, rect.left, rect.top)
        right, bottom = logical_to_physical(hwnd, rect.right, rect.bottom)
        width = right - left
        height = bottom - top
        if width >= 400 and height >= 300:
            found.append((int(hwnd), left, top, right, bottom, title))
        return True

    callback = enum_proc(_enum)
    user32.EnumWindows(callback, 0)
    if not found and _last_game_hwnd and user32.IsWindow(_last_game_hwnd):
        hwnd = _last_game_hwnd
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        left, top = logical_to_physical(hwnd, rect.left, rect.top)
        right, bottom = logical_to_physical(hwnd, rect.right, rect.bottom)
        width = right - left
        height = bottom - top
        if width >= 400 and height >= 300:
            found.append((int(hwnd), left, top, right, bottom, ""))
    if not found:
        _game_hwnd = None
        return None
    found.sort(key=lambda item: (item[3] - item[1]) * (item[4] - item[2]), reverse=True)
    hwnd, left, top, right, bottom, title = found[0]
    _game_hwnd = hwnd
    _last_game_hwnd = hwnd
    return (left, top, right, bottom, title)


def capture_for_search() -> tuple[np.ndarray, int, int]:
    """Grab the game window only. Fallback is the full desktop."""
    from window_capture import client_origin, grab_hwnd

    game = find_game_window()
    if game is not None and _game_hwnd is not None:
        hwnd = _game_hwnd
        image = grab_hwnd(hwnd)
        if image is not None:
            origin_x, origin_y = client_origin(hwnd)
            return image, origin_x, origin_y
        left, top, right, bottom, _title = game
        image = _grab_mss_region(left, top, right - left, bottom - top)
        return image, left, top
    image = grab_desktop()
    return image, _desktop_origin[0], _desktop_origin[1]


def find_label_on_desktop(screen_bgr: np.ndarray) -> tuple[tuple[int, int, int, int] | None, float]:
    """Kept for tests; prefer capture_for_search in the app."""
    game = find_game_window()
    if game is None:
        return find_label(screen_bgr)
    left, top, right, bottom, _title = game
    origin_x, origin_y = _desktop_origin
    x0 = left - origin_x
    y0 = top - origin_y
    x1 = right - origin_x
    y1 = bottom - origin_y
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(screen_bgr.shape[1], x1)
    y1 = min(screen_bgr.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        return find_label(screen_bgr)
    crop = screen_bgr[y0:y1, x0:x1]
    rect, score = find_label(crop)
    if rect is None:
        return None, score
    rx, ry, rw, rh = rect
    return (rx + x0, ry + y0, rw, rh), score
