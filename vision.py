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

from exp_parser import parse_exp

ASSETS = Path(__file__).resolve().parent / "assets"
LABEL_PATH = ASSETS / "exp_label.png"

# exp_label.png was cropped from exp_bar.png at this top-left.
LABEL_IN_BAR = (8, 8)
MATCH_THRESHOLD = 0.78
OCR_WIDTH = 150
OCR_HEIGHT = 22

_ocr: RapidOCR | None = None
_label_bgr: np.ndarray | None = None
_sct = None
_desktop_origin = (0, 0)


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
    _ensure_sct()


def find_label(screen_bgr: np.ndarray) -> tuple[tuple[int, int, int, int] | None, float]:
    templ = _load_label()
    screen_g = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    templ_g = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    if screen_g.shape[0] < templ_g.shape[0] or screen_g.shape[1] < templ_g.shape[1]:
        return None, 0.0
    result = cv2.matchTemplate(screen_g, templ_g, cv2.TM_CCOEFF_NORMED)
    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
    if max_val < MATCH_THRESHOLD:
        return None, float(max_val)
    h, w = templ_g.shape
    return (int(max_loc[0]), int(max_loc[1]), int(w), int(h)), float(max_val)


def label_rect_to_ocr_rect(
    label_rect: tuple[int, int, int, int],
    screen_w: int,
    screen_h: int,
) -> tuple[int, int, int, int]:
    x, y, _w, _h = label_rect
    ox = max(0, x - LABEL_IN_BAR[0])
    oy = max(0, y - 2)
    width = min(OCR_WIDTH, screen_w - ox)
    height = min(OCR_HEIGHT, screen_h - oy)
    return (ox, oy, width, height)


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
    h, _w = image_bgr.shape[:2]
    if h > 28:
        image_bgr = image_bgr[:22]
    result, _elapse = get_ocr()(image_bgr)
    if not result:
        return None
    text = " ".join(item[1] for item in result)
    return parse_exp(text)


def _ensure_sct():
    global _sct, _desktop_origin
    if _sct is None:
        import mss

        _sct = mss.mss()
        monitor = _sct.monitors[0]
        _desktop_origin = (int(monitor["left"]), int(monitor["top"]))
    return _sct


def grab_region(left: int, top: int, width: int, height: int) -> np.ndarray:
    sct = _ensure_sct()
    frame = np.array(
        sct.grab({"left": left, "top": top, "width": max(1, width), "height": max(1, height)})
    )
    return frame[:, :, :3]


def grab_desktop() -> np.ndarray:
    sct = _ensure_sct()
    monitor = sct.monitors[0]
    global _desktop_origin
    _desktop_origin = (int(monitor["left"]), int(monitor["top"]))
    frame = np.array(sct.grab(monitor))
    return frame[:, :, :3]


def find_game_window() -> tuple[int, int, int, int, str] | None:
    """Return (left, top, right, bottom, title) in virtual-screen coordinates."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found: list[tuple[int, int, int, int, str]] = []

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
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width >= 400 and height >= 300:
            found.append((rect.left, rect.top, rect.right, rect.bottom, title))
        return True

    callback = enum_proc(_enum)
    user32.EnumWindows(callback, 0)
    if not found:
        return None
    found.sort(key=lambda item: (item[2] - item[0]) * (item[3] - item[1]), reverse=True)
    return found[0]


def capture_for_search() -> tuple[np.ndarray, int, int]:
    """Grab the game window only. Fallback is the full desktop."""
    game = find_game_window()
    if game is not None:
        left, top, right, bottom, _title = game
        image = grab_region(left, top, right - left, bottom - top)
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
