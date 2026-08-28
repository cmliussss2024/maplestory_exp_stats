"""MapleStory EXP rate window."""

from __future__ import annotations

# Must run before tkinter / OpenCV import, or Windows locks in per-monitor DPI
# and the window shrinks/rebuilds when dragged onto a 150% display.
from dpi import disable_per_monitor_dpi

disable_per_monitor_dpi()

import time
import tkinter as tk
from pathlib import Path

import cv2
from PIL import Image, ImageTk

from locator import Locator, LocatorState
from rate_tracker import CHART_TABS, RATE_ROWS, RateTracker, Rates
from ui import ExpRateWindow, WINDOW_PATH, paint_chart
from ui.drawing import fit_image
from ui.styles import Spacing, Type
from ui.views.overlay_window import OverlayWindow
from ui.overlay_log import overlay_log
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
DEFAULT_CHART_TAB = 0
LOCK_SCAN_MS = 1000
SEARCH_SCAN_MS = Locator.SEARCH_INTERVAL_SECONDS * 1000

STATUS_TEXT = {
    LocatorState.SEARCHING: "定位中",
    LocatorState.LOCKED: "监控中",
    LocatorState.RELOCATING: "重新定位",
    LocatorState.FAILED: "读取失败",
}


def _fmt(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class ExpRateApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("经验增速")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.locator = Locator()
        self.current = RateTracker()
        self.session = RateTracker(history_path=HISTORY_PATH)
        self._busy = False
        self._closed = False
        self._last_exp: int | None = None
        self._window_placed = False
        self._tick_job: str | None = None
        self._ui_job: str | None = None
        self._save_pos_job: str | None = None
        self._last_saved_pos: tuple[int, int] | None = None
        self._last_gain_series: tuple | None = None
        self._last_total_series: tuple | None = None
        self._float: OverlayWindow | None = None
        self._overlay_scale = 1.0

        self.current_vars = {key: tk.StringVar(value="0") for key, _label in RATE_ROWS}
        self.session_vars = {key: tk.StringVar(value="0") for key, _label in RATE_ROWS}
        self.current_exp = tk.StringVar(value="—")
        self.session_exp = tk.StringVar(value="0")
        self.session_time = tk.StringVar(value="—")
        self.status = tk.StringVar(value=STATUS_TEXT[LocatorState.SEARCHING])
        self._chart_span = CHART_TABS[DEFAULT_CHART_TAB][1]
        self._chart_step = CHART_TABS[DEFAULT_CHART_TAB][2]
        self._chart_ago = CHART_TABS[DEFAULT_CHART_TAB][3]
        self._chart_gain_suffix = CHART_TABS[DEFAULT_CHART_TAB][4]
        self._chart_rate_target = CHART_TABS[DEFAULT_CHART_TAB][5]
        self._chart_tab_index = DEFAULT_CHART_TAB

        self.window = ExpRateWindow(
            root,
            current_vars=self.current_vars,
            session_vars=self.session_vars,
            current_exp=self.current_exp,
            session_exp=self.session_exp,
            session_time=self.session_time,
            status=self.status,
            on_clear_current=self.clear_current,
            on_clear_session=self.clear_session,
            on_retry=self.retry,
            on_tab_select=self._select_chart_tab,
            on_float=self.enter_float,
        )
        self.retry_btn = self.window.retry_row.button
        self.status_label = self.window.info_section.status_label
        self.gain_chart = self.window.chart_section.gain_chart
        self.total_chart = self.window.chart_section.total_chart
        self.window.chart_section.draw_tabs(DEFAULT_CHART_TAB)

        self._restore_position()
        self.root.after_idle(self.window.rate_section.sync_divider)
        self.root.after_idle(self._mark_window_placed)
        self.root.bind("<Configure>", self._on_root_configure)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        now = time.time()
        self._refresh_rates(now)
        self._redraw_chart(now)
        if self.session.last_exp is not None:
            self._last_exp = self.session.last_exp
            self.current_exp.set(_fmt(self._last_exp))
        self._tick_job = self.root.after(200, self.tick)
        self._ui_job = self.root.after(1000, self._ui_tick)

    def enter_float(self) -> None:
        if self._float is not None:
            return
        self.root.update_idletasks()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        overlay_log(
            "enter_float",
            x=x,
            y=y,
            scale=round(self._overlay_scale, 4),
            root=self.root.geometry(),
            tk_in=round(float(self.root.winfo_fpixels("1i")), 2),
        )
        self._float = OverlayWindow(
            self.root,
            vars_map=self.current_vars,
            on_restore=self.exit_float,
            x=x,
            y=y,
            scale=self._overlay_scale,
        )
        self.root.withdraw()

    def exit_float(self) -> None:
        overlay = self._float
        self._float = None
        pos = overlay.position() if overlay is not None else None
        if overlay is not None:
            overlay_log("exit_float", scale=round(overlay.scale, 4), pos=pos)
            self._overlay_scale = overlay.scale
            overlay.destroy()
        self.root.deiconify()
        if pos is not None:
            self.root.geometry(f"+{pos[0]}+{pos[1]}")
        self.root.attributes("-topmost", True)
        self.root.lift()

    def _mark_window_placed(self) -> None:
        self._window_placed = True

    def _restore_position(self) -> None:
        saved = load_window_position(WINDOW_PATH)
        if saved is None:
            return
        x, y = saved
        self.root.geometry(f"+{x}+{y}")

    def _on_root_configure(self, event: tk.Event) -> None:
        if self._float is not None:
            return
        if event.widget is not self.root or not self._window_placed:
            return
        if self._save_pos_job is not None:
            self.root.after_cancel(self._save_pos_job)
        self._save_pos_job = self.root.after(150, self._persist_position)

    def _persist_position(self) -> None:
        self._save_pos_job = None
        if not self.root.winfo_exists() or not self.root.winfo_ismapped():
            return
        pos = (self.root.winfo_x(), self.root.winfo_y())
        if pos == self._last_saved_pos:
            return
        self._last_saved_pos = pos
        save_window_position(WINDOW_PATH, pos[0], pos[1])

    def _on_close(self) -> None:
        self._closed = True
        for attr in ("_tick_job", "_ui_job", "_save_pos_job"):
            job = getattr(self, attr)
            if job is None:
                continue
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
            setattr(self, attr, None)
        try:
            from window_capture import shutdown_capture

            shutdown_capture()
        except Exception:
            pass
        if self._float is not None:
            pos = self._float.position()
            overlay = self._float
            overlay_log("close_float", scale=round(overlay.scale, 4), pos=pos)
            self._overlay_scale = overlay.scale
            self._float = None
            overlay.destroy()
            save_window_position(WINDOW_PATH, pos[0], pos[1])
            self.root.destroy()
            return
        self.root.update_idletasks()
        self._persist_position()
        self.root.destroy()

    def retry(self) -> None:
        self.locator.retry()
        self._refresh_status()

    def clear_current(self) -> None:
        self.current.clear()
        self._refresh_rates(time.time())

    def clear_session(self) -> None:
        self.session.clear()
        self._refresh_rates(time.time())
        self._redraw_chart(time.time())

    def _refresh_status(self) -> None:
        self.status.set(STATUS_TEXT[self.locator.state])
        if self.locator.state == LocatorState.FAILED:
            self.status_label.configure(foreground=Type.status_error)
            self.retry_btn.configure(state="normal")
        else:
            self.status_label.configure(foreground=Type.status_ok)
            self.retry_btn.configure(state="disabled")

    def _apply_column(self, vars_map: dict[str, tk.StringVar], rates: Rates) -> None:
        vars_map["per_sec"].set(_fmt(rates.per_sec))
        vars_map["per_min"].set(_fmt(rates.per_min))
        vars_map["per_5min"].set(_fmt(rates.per_5min))
        vars_map["per_hour"].set(_fmt(rates.per_hour))

    def _refresh_rates(self, now: float) -> None:
        self._apply_column(self.current_vars, self.current.hourly_rates(now))
        self._apply_column(self.session_vars, self.session.hourly_rates(now))
        self.session_exp.set(_fmt(self.session.total_gained()))
        self.session_time.set(_fmt_duration(self.session.elapsed_since_first_gain(now)))

    def _ui_tick(self) -> None:
        if self._closed or not self.root.winfo_exists():
            return
        now = time.time()
        self.current.clear_if_idle(now)
        self._refresh_rates(now)
        self._redraw_chart(now)
        self._ui_job = self.root.after(1000, self._ui_tick)

    def tick(self) -> None:
        if self._closed or not self.root.winfo_exists():
            return
        delay = (
            LOCK_SCAN_MS
            if self.locator.state == LocatorState.LOCKED
            else SEARCH_SCAN_MS
        )
        if self._busy:
            self._tick_job = self.root.after(delay, self.tick)
            return
        self._busy = True
        try:
            self._scan_once()
        except Exception as exc:
            overlay_log("scan_error", error=repr(exc))
        finally:
            self._busy = False
            if self._closed or not self.root.winfo_exists():
                return
            self._refresh_status()
            self._tick_job = self.root.after(delay, self.tick)

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
        self.current.tick(exp, now)
        self.session.tick(exp, now)
        if exp is not None:
            self._last_exp = exp
        elif self.session.last_exp is not None:
            self._last_exp = self.session.last_exp
        elif self.current.last_exp is not None:
            self._last_exp = self.current.last_exp
        if self._last_exp is not None:
            self.current_exp.set(_fmt(self._last_exp))
        self._refresh_rates(now)

    def _update_preview(self, crop_bgr) -> None:
        if crop_bgr is None or crop_bgr.size == 0:
            return
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        slot = self.window.info_section.image_canvas
        r, g, b = slot.winfo_rgb(slot.cget("bg"))
        image = fit_image(
            Image.fromarray(rgb),
            Spacing.preview_width,
            Spacing.preview_height,
            fill=(r // 256, g // 256, b // 256),
        )
        photo = ImageTk.PhotoImage(image)
        self.window.info_section.set_image(photo)

    def _select_chart_tab(self, index: int) -> None:
        if index == self._chart_tab_index:
            return
        self._chart_tab_index = index
        self._last_gain_series = None
        self._last_total_series = None
        self.window.chart_section.draw_tabs(index)
        _label, span, step, ago, gain_suffix, rate_target, gain_title = CHART_TABS[index]
        self._chart_span = span
        self._chart_step = step
        self._chart_ago = ago
        self._chart_gain_suffix = gain_suffix
        self._chart_rate_target = rate_target
        self.window.chart_section.set_gain_title(gain_title)
        self._redraw_chart(time.time())

    def _redraw_chart(self, now: float) -> None:
        axis_start = self.session.chart_axis_start_label(now, self._chart_span, self._chart_ago)
        gain = self.session.chart_rate_series(
            now,
            span=self._chart_span,
            step=self._chart_step,
            target=self._chart_rate_target,
        )
        total = self.session.cumulative_series(now, span=self._chart_span, step=self._chart_step)
        gain_key = (tuple(gain), axis_start, self._chart_gain_suffix)
        total_key = (tuple(total), axis_start)
        if gain_key != self._last_gain_series:
            self._last_gain_series = gain_key
            paint_chart(
                self.gain_chart,
                gain,
                suffix=self._chart_gain_suffix,
                line=Type.gain_line,
                fill=Type.gain_fill,
                axis_start=axis_start,
            )
        if total_key != self._last_total_series:
            self._last_total_series = total_key
            paint_chart(
                self.total_chart,
                total,
                suffix="",
                line=Type.total_line,
                fill=Type.total_fill,
                axis_start=axis_start,
            )


def main() -> None:
    warmup()
    root = tk.Tk()
    ExpRateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
