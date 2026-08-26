"""MapleStory EXP rate window."""

from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from locator import Locator, LocatorState
from rate_tracker import RateTracker, Rates
from vision import (
    capture_for_search,
    find_label,
    grab_region,
    label_present,
    label_rect_to_ocr_rect,
    read_exp_from_bgr,
    to_virtual_rect,
    warmup,
)

from window_position import load_window_position, save_window_position

HISTORY_PATH = Path(__file__).resolve().parent / "data" / "exp_history.jsonl"
WINDOW_PATH = Path(__file__).resolve().parent / "data" / "window.json"

STATUS_TEXT = {
    LocatorState.SEARCHING: "定位中",
    LocatorState.LOCKED: "读取中",
    LocatorState.RELOCATING: "重新定位",
    LocatorState.FAILED: "读取失败",
}


def _fmt(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


class ExpRateApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("经验增速")
        self.root.resizable(False, False)
        self.locator = Locator()
        self.tracker = RateTracker(history_path=HISTORY_PATH)
        self._busy = False

        pad = {"padx": 16, "pady": 4}
        self.rt_second = tk.StringVar(value="0")
        self.rt_minute = tk.StringVar(value="0")
        self.rt_hour = tk.StringVar(value="0")
        self.avg_second = tk.StringVar(value="0")
        self.avg_minute = tk.StringVar(value="0")
        self.avg_hour = tk.StringVar(value="0")
        self.current_exp = tk.StringVar(value="—")
        self.status = tk.StringVar(value=STATUS_TEXT[LocatorState.SEARCHING])

        header = ("Microsoft YaHei UI", 10)
        label_font = ("Microsoft YaHei UI", 11)
        value_font = ("Microsoft YaHei UI", 16, "bold")

        ttk.Label(root, text="", font=header).grid(row=0, column=0, sticky="w", **pad)
        ttk.Label(root, text="实时", font=header).grid(row=0, column=1, sticky="e", **pad)
        ttk.Label(root, text="平均", font=header).grid(row=0, column=2, sticky="e", **pad)

        ttk.Label(root, text="每秒", font=label_font).grid(row=1, column=0, sticky="w", **pad)
        ttk.Label(root, textvariable=self.rt_second, font=value_font).grid(
            row=1, column=1, sticky="e", **pad
        )
        ttk.Label(root, textvariable=self.avg_second, font=value_font).grid(
            row=1, column=2, sticky="e", **pad
        )

        ttk.Label(root, text="每分钟", font=label_font).grid(row=2, column=0, sticky="w", **pad)
        ttk.Label(root, textvariable=self.rt_minute, font=value_font).grid(
            row=2, column=1, sticky="e", **pad
        )
        ttk.Label(root, textvariable=self.avg_minute, font=value_font).grid(
            row=2, column=2, sticky="e", **pad
        )

        ttk.Label(root, text="每小时", font=label_font).grid(row=3, column=0, sticky="w", **pad)
        ttk.Label(root, textvariable=self.rt_hour, font=value_font).grid(
            row=3, column=1, sticky="e", **pad
        )
        ttk.Label(root, textvariable=self.avg_hour, font=value_font).grid(
            row=3, column=2, sticky="e", **pad
        )

        ttk.Separator(root).grid(row=4, column=0, columnspan=3, sticky="ew", pady=8)

        ttk.Label(root, text="当前经验", font=("Microsoft YaHei UI", 10)).grid(
            row=5, column=0, sticky="w", **pad
        )
        ttk.Label(root, textvariable=self.current_exp, font=("Microsoft YaHei UI", 12)).grid(
            row=5, column=1, columnspan=2, sticky="e", **pad
        )

        ttk.Label(root, text="状态", font=("Microsoft YaHei UI", 10)).grid(
            row=6, column=0, sticky="w", **pad
        )
        ttk.Label(root, textvariable=self.status, font=("Microsoft YaHei UI", 12)).grid(
            row=6, column=1, columnspan=2, sticky="e", **pad
        )

        self.retry_btn = ttk.Button(root, text="重试", command=self.retry, state="disabled")
        self.retry_btn.grid(row=7, column=0, pady=(8, 8), padx=16, sticky="w")

        ttk.Label(
            root,
            text="实时：这一秒增量　平均：按已过去的时间折算",
            font=("Microsoft YaHei UI", 9),
            foreground="#666",
        ).grid(row=8, column=0, columnspan=3, pady=(0, 8))

        ttk.Label(
            root,
            text="窗口模式打开冒险岛后即可读取底部经验条",
            font=("Microsoft YaHei UI", 9),
            foreground="#666",
        ).grid(row=9, column=0, columnspan=3, pady=(0, 8))

        self.preview = ttk.Label(root)
        self.preview.grid(row=10, column=0, columnspan=3, pady=(0, 12))

        self._restore_position()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(200, self.tick)

    def _restore_position(self) -> None:
        saved = load_window_position(WINDOW_PATH)
        if saved is None:
            return
        x, y = saved
        self.root.geometry(f"+{x}+{y}")

    def _on_close(self) -> None:
        self.root.update_idletasks()
        save_window_position(WINDOW_PATH, self.root.winfo_x(), self.root.winfo_y())
        self.root.destroy()

    def retry(self) -> None:
        self.locator.retry()
        self._refresh_status()

    def _refresh_status(self) -> None:
        self.status.set(STATUS_TEXT[self.locator.state])
        if self.locator.state == LocatorState.FAILED:
            self.retry_btn.configure(state="normal")
        else:
            self.retry_btn.configure(state="disabled")

    def _apply_rates(self, realtime: Rates, average: Rates) -> None:
        self.rt_second.set(_fmt(realtime.per_second))
        self.rt_minute.set(_fmt(realtime.per_minute))
        self.rt_hour.set(_fmt(realtime.per_hour))
        self.avg_second.set(_fmt(average.per_second))
        self.avg_minute.set(_fmt(average.per_minute))
        self.avg_hour.set(_fmt(average.per_hour))

    def tick(self) -> None:
        if self._busy:
            self.root.after(1000, self.tick)
            return
        self._busy = True
        try:
            self._scan_once()
        finally:
            self._busy = False
            self._refresh_status()
            self.root.after(1000, self.tick)

    def _scan_once(self) -> None:
        if self.locator.state == LocatorState.FAILED:
            return
        now = time.time()

        if self.locator.state in (LocatorState.SEARCHING, LocatorState.RELOCATING):
            image, origin_x, origin_y = capture_for_search()
            label_rect, _score = find_label(image)
            virtual_ocr = None
            if label_rect is not None:
                h, w = image.shape[:2]
                ocr_rect = label_rect_to_ocr_rect(label_rect, w, h)
                virtual_ocr = to_virtual_rect(ocr_rect, (origin_x, origin_y))
            self.locator.on_search_result(virtual_ocr)
            if self.locator.state == LocatorState.LOCKED and virtual_ocr is not None:
                self._consume_crop(grab_region(*virtual_ocr), now)
            return

        if self.locator.state == LocatorState.LOCKED and self.locator.locked_rect is not None:
            crop = grab_region(*self.locator.locked_rect)
            found = label_present(crop)
            self.locator.on_lock_check(found)
            if found:
                self._consume_crop(crop, now)

    def _consume_crop(self, crop, now: float) -> None:
        self._update_preview(crop)
        exp = read_exp_from_bgr(crop)
        self.tracker.tick(exp, now)
        if self.tracker.last_exp is not None:
            self.current_exp.set(_fmt(self.tracker.last_exp))
        self._apply_rates(
            self.tracker.compute(now, "realtime"),
            self.tracker.compute(now, "average"),
        )

    def _update_preview(self, crop_bgr) -> None:
        if crop_bgr is None or crop_bgr.size == 0:
            return
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image = image.resize(
            (max(image.width * 2, 1), max(image.height * 2, 1)),
            Image.Resampling.NEAREST,
        )
        photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=photo)
        self.preview.image = photo


def main() -> None:
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    warmup()
    root = tk.Tk()
    ExpRateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
