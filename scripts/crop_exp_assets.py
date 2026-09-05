"""Crop EXP assets from a live desktop search hit.

    python scripts/crop_exp_assets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vision import (  # noqa: E402
    ASSETS,
    LABEL_IN_BAR,
    OCR_HEIGHT,
    OCR_WIDTH,
    _load_label,
    crop_bgr,
    find_label,
    grab_region,
    label_rect_to_ocr_rect,
    list_physical_monitors,
    read_exp_reading_from_bgr,
    search_exp_label,
)

# EXP cell at 1080p 1x, relative to the 24x13 label: inset (7, 5), size 134x38.
# Drops HUD chrome; keeps the dark rounded chip and the progress-bar cap.
_BAR_INSET_X = 7 / 24
_BAR_INSET_Y = 5 / 13
_BAR_W = 134 / 24
_BAR_H = 38 / 13


def _clamp_rect(
    x: int, y: int, w: int, h: int, screen_w: int, screen_h: int
) -> tuple[int, int, int, int]:
    x = max(0, x)
    y = max(0, y)
    w = max(1, min(w, screen_w - x))
    h = max(1, min(h, screen_h - y))
    return x, y, w, h


def main() -> None:
    virtual_ocr, monitor_index = search_exp_label()
    if virtual_ocr is None:
        raise SystemExit("EXP label not found on any monitor")

    monitors = {m["index"]: m for m in list_physical_monitors()}
    monitor = monitors.get(monitor_index) if monitor_index is not None else None
    if monitor is None:
        raise SystemExit(f"monitor {monitor_index} missing after hit")

    left = monitor["left"]
    top = monitor["top"]
    width = monitor["width"]
    height = monitor["height"]
    image = grab_region(left, top, width, height)
    screen_h, screen_w = image.shape[:2]
    label_rect, score = find_label(image)
    if label_rect is None:
        raise SystemExit(f"label not found on monitor {monitor_index} score={score:.4f}")

    lx, ly, lw, lh = label_rect
    native_w = _load_label().shape[1]
    scale = lw / native_w
    bx = int(round(lx - _BAR_INSET_X * lw))
    by = int(round(ly - _BAR_INSET_Y * lh))
    bw = int(round(_BAR_W * lw))
    bh = int(round(_BAR_H * lh))
    bar_rect = _clamp_rect(bx, by, bw, bh, screen_w, screen_h)
    ocr_rect = label_rect_to_ocr_rect(label_rect, screen_w, screen_h)

    label = crop_bgr(image, label_rect)
    bar = crop_bgr(image, bar_rect)
    ocr_crop = crop_bgr(image, ocr_rect)
    reading = read_exp_reading_from_bgr(ocr_crop)

    ASSETS.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(ASSETS / "exp_label.png"), label)
    cv2.imwrite(str(ASSETS / "exp_bar.png"), bar)
    cv2.imwrite(str(ASSETS / "exp_ocr.png"), ocr_crop)

    print(f"monitor={monitor_index} {width}x{height} at {left},{top}")
    print(f"search_ocr={virtual_ocr}")
    print(f"capture={screen_w}x{screen_h}")
    print(f"label={label_rect} score={score:.4f} scale={scale:.4f}")
    print(f"bar={bar_rect} ocr={ocr_rect} constants={OCR_WIDTH}x{OCR_HEIGHT} inset={LABEL_IN_BAR}")
    print(f"wrote {label.shape[1]}x{label.shape[0]} exp_label.png")
    print(f"wrote {bar.shape[1]}x{bar.shape[0]} exp_bar.png")
    print(f"wrote {ocr_crop.shape[1]}x{ocr_crop.shape[0]} exp_ocr.png reading={reading}")


if __name__ == "__main__":
    main()
