"""Screen capture, EXP-label matching, and OCR."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

from exp_parser import ExpReading, pick_exp_reading
from paths import assets_dir

ASSETS = assets_dir()
LABEL_PATH = ASSETS / "exp_label.png"

# Locked crop relative to the EXP label: tight around text + yellow-green slot.
# Native size is 1920x1080 on screen 2 @ 1x. Screen 1 1366x768 @ 1.5x matches at 1.5.
LABEL_IN_BAR = (1, 2)
MATCH_THRESHOLD = 0.90
CONFIDENT_MATCH = 0.95
OCR_WIDTH = 121
OCR_HEIGHT = 34
TEXT_ROW_HEIGHT = 16
OCR_UPSCALE = 3
NEIGHBORHOOD_PAD = 300
BOTTOM_BAND_FRACTION = 0.30
_LABEL_SCALES = (
    1.0, 1.25, 1.5, 1.75, 2.0, 0.75, 2.25, 2.5, 1.1, 1.35, 1.6, 1.85, 0.5, 3.0,
)
_SCALES_1_0 = (1.0, 1.1, 0.75, 1.25, 1.35)
_SCALES_1_5 = (1.5, 1.35, 1.6, 1.75, 1.25)

_ocr: RapidOCR | None = None
_label_bgr: np.ndarray | None = None
_tls = threading.local()

GrabFn = Callable[[int, int, int, int], np.ndarray]
MonitorsFn = Callable[[], list[dict[str, int]]]
DpiFn = Callable[[int, int], float]


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


def scales_for_dpi(dpi: float) -> tuple[float, ...]:
    if dpi >= 1.35:
        return _SCALES_1_5
    return _SCALES_1_0


def find_label(
    screen_bgr: np.ndarray,
    scales: tuple[float, ...] | None = None,
) -> tuple[tuple[int, int, int, int] | None, float]:
    templ = _load_label()
    screen_g = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    templ_g = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
    th0, tw0 = templ_g.shape
    best_val = -1.0
    best_rect: tuple[int, int, int, int] | None = None
    for scale in scales if scales is not None else _LABEL_SCALES:
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
    reading = read_exp_reading_from_bgr(image_bgr)
    return None if reading is None else reading.exp


def read_exp_reading_from_bgr(image_bgr: np.ndarray) -> ExpReading | None:
    if image_bgr.size == 0:
        return None
    readings: list[tuple[str, float]] = []
    for view in _ocr_views(image_bgr):
        text, conf = _ocr_text(view)
        if text:
            readings.append((text, conf))
    return pick_exp_reading(readings)


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
    from dpi import physical_call

    return physical_call(_mss_grab_impl, left, top, width, height)


def _thread_mss():
    import mss

    sct = getattr(_tls, "sct", None)
    if sct is None:
        sct = mss.mss()
        _tls.sct = sct
    return sct


def _mss_grab_impl(left: int, top: int, width: int, height: int) -> np.ndarray:
    # mss GDI handles are thread-affine. physical_call keeps one worker, so this
    # instance stays on that thread for the process lifetime.
    sct = _thread_mss()
    frame = np.array(
        sct.grab({"left": left, "top": top, "width": max(1, width), "height": max(1, height)})
    )
    return frame[:, :, :3]


def list_physical_monitors() -> list[dict[str, int]]:
    from dpi import physical_call

    return physical_call(_list_monitors_impl)


def _list_monitors_impl() -> list[dict[str, int]]:
    sct = _thread_mss()
    monitors: list[dict[str, int]] = []
    for index, monitor in enumerate(sct.monitors[1:], start=1):
        monitors.append(
            {
                "index": index,
                "left": int(monitor["left"]),
                "top": int(monitor["top"]),
                "width": int(monitor["width"]),
                "height": int(monitor["height"]),
            }
        )
    return monitors


def _virtual_bounds(monitors: list[dict[str, int]]) -> tuple[int, int, int, int]:
    left = min(m["left"] for m in monitors)
    top = min(m["top"] for m in monitors)
    right = max(m["left"] + m["width"] for m in monitors)
    bottom = max(m["top"] + m["height"] for m in monitors)
    return left, top, right, bottom


def _clamp_rect(
    left: int, top: int, width: int, height: int, bounds: tuple[int, int, int, int]
) -> tuple[int, int, int, int] | None:
    b_left, b_top, b_right, b_bottom = bounds
    x0 = max(left, b_left)
    y0 = max(top, b_top)
    x1 = min(left + width, b_right)
    y1 = min(top + height, b_bottom)
    if x1 - x0 < 8 or y1 - y0 < 6:
        return None
    return x0, y0, x1 - x0, y1 - y0


def _match_grab(
    left: int,
    top: int,
    width: int,
    height: int,
    scales: tuple[float, ...],
    grab_fn: GrabFn,
) -> tuple[tuple[int, int, int, int] | None, float]:
    if width < 8 or height < 6:
        return None, 0.0
    image = grab_fn(left, top, width, height)
    label_rect, score = find_label(image, scales=scales)
    if label_rect is None:
        return None, score
    h, w = image.shape[:2]
    ocr_rect = label_rect_to_ocr_rect(label_rect, w, h)
    return to_virtual_rect(ocr_rect, (left, top)), score


def _ordered_monitors(
    monitors: list[dict[str, int]], last_monitor_index: int | None
) -> list[dict[str, int]]:
    if last_monitor_index is None:
        return list(monitors)
    preferred = [m for m in monitors if m["index"] == last_monitor_index]
    rest = [m for m in monitors if m["index"] != last_monitor_index]
    return preferred + rest


def search_exp_label(
    *,
    last_rect: tuple[int, int, int, int] | None = None,
    last_monitor_index: int | None = None,
    grab_fn: GrabFn | None = None,
    monitors_fn: MonitorsFn | None = None,
    dpi_fn: DpiFn | None = None,
) -> tuple[tuple[int, int, int, int] | None, int | None]:
    """Neighborhood → per monitor bottom band then upper remainder. Never monitors[0].

    Picks the highest-scoring hit so IDE text like ``maplestory_exp_stats`` does not
    beat the real game label. Stops early only on a confident match.
    """
    from dpi import dpi_scale_at

    grab = grab_fn or grab_region
    monitors = (monitors_fn or list_physical_monitors)()
    if not monitors:
        return None, None
    dpi_at = dpi_fn or dpi_scale_at
    bounds = _virtual_bounds(monitors)
    best: tuple[float, tuple[int, int, int, int], int | None] | None = None

    def _consider(
        hit: tuple[int, int, int, int] | None, score: float, mon: int | None
    ) -> tuple[tuple[int, int, int, int], int | None] | None:
        nonlocal best
        if hit is None or score < MATCH_THRESHOLD:
            return None
        if best is None or score > best[0]:
            best = (score, hit, mon)
        if score >= CONFIDENT_MATCH:
            return hit, mon
        return None

    if last_rect is not None:
        lx, ly, lw, lh = last_rect
        pad = NEIGHBORHOOD_PAD
        region = _clamp_rect(lx - pad, ly - pad, lw + 2 * pad, lh + 2 * pad, bounds)
        if region is not None:
            cx = region[0] + region[2] // 2
            cy = region[1] + region[3] // 2
            hit, score = _match_grab(*region, scales_for_dpi(dpi_at(cx, cy)), grab)
            mon = last_monitor_index
            if hit is not None and mon is None:
                mon = _monitor_index_for_point(
                    hit[0] + hit[2] // 2, hit[1] + hit[3] // 2, monitors
                )
            early = _consider(hit, score, mon)
            if early is not None:
                return early

    for monitor in _ordered_monitors(monitors, last_monitor_index):
        left = monitor["left"]
        top = monitor["top"]
        width = monitor["width"]
        height = monitor["height"]
        scales = scales_for_dpi(dpi_at(left + width // 2, top + height // 2))
        band_h = max(1, int(round(height * BOTTOM_BAND_FRACTION)))
        band_top = top + height - band_h
        hit, score = _match_grab(left, band_top, width, band_h, scales, grab)
        early = _consider(hit, score, monitor["index"])
        if early is not None:
            return early
        upper_h = height - band_h
        if upper_h >= 6:
            hit, score = _match_grab(left, top, width, upper_h, scales, grab)
            early = _consider(hit, score, monitor["index"])
            if early is not None:
                return early

    if best is None:
        return None, None
    return best[1], best[2]


def _monitor_index_for_point(
    x: int, y: int, monitors: list[dict[str, int]]
) -> int | None:
    for monitor in monitors:
        if (
            monitor["left"] <= x < monitor["left"] + monitor["width"]
            and monitor["top"] <= y < monitor["top"] + monitor["height"]
        ):
            return monitor["index"]
    return monitors[0]["index"] if monitors else None
