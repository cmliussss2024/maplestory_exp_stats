"""MapleStory EXP rate window."""

from __future__ import annotations

# Must run before tkinter / OpenCV import, or Windows locks in per-monitor DPI
# and the window shrinks/rebuilds when dragged onto a 150% display.
from dpi import disable_per_monitor_dpi

disable_per_monitor_dpi()

import math
import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk

from locator import Locator, LocatorState
from exp_parser import ExpReading
from paths import data_dir
from rate_tracker import CHARTS, RATE_ROWS, RateTracker, Rates, eta_to_level
from ui import ExpRateWindow, WINDOW_PATH, paint_chart
from ui.drawing import fit_image
from ui.styles import Spacing, Type
from ui.views.overlay_window import OverlayWindow
from vision import (
    grab_region,
    label_present,
    read_exp_reading_from_bgr,
    search_exp_label,
    warmup,
)

from window_position import load_window_position, save_window_position

HISTORY_PATH = data_dir() / "exp_history.jsonl"
LOCK_SCAN_MS = 1000
SEARCH_SCAN_MS = Locator.SEARCH_INTERVAL_SECONDS * 1000

STATUS_TEXT = {
    LocatorState.SEARCHING: "定位中",
    LocatorState.LOCKED: "监控中",
    LocatorState.RELOCATING: "重新定位中",
    LocatorState.FAILED: "读取失败",
}

STATUS_COLOR = {
    LocatorState.SEARCHING: Type.Info.status_search,
    LocatorState.LOCKED: Type.Info.status_ok,
    LocatorState.RELOCATING: Type.Info.status_search,
    LocatorState.FAILED: Type.Info.status_error,
}


def _fmt(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}"


def _fmt_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}%"


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class ExpRateApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("经验统计助手")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.locator = Locator()
        self.current = RateTracker()
        self.session = RateTracker(history_path=HISTORY_PATH)
        self._busy = False
        self._closed = False
        self._accepted_percent: float | None = None
        self._window_placed = False
        self._tick_job: str | None = None
        self._ui_job: str | None = None
        self._scan_due_at = 0.0
        self._save_pos_job: str | None = None
        self._last_saved_pos: tuple[int, int] | None = None
        self._last_gain_series: tuple | None = None
        self._last_total_series: tuple | None = None
        self._float: OverlayWindow | None = None
        self._overlay_scale = 1.0

        self.current_vars = {key: tk.StringVar(value="0") for key, _label in RATE_ROWS}
        self.current_exp = tk.StringVar(value="-")
        self.current_percent = tk.StringVar(value="-")
        self.session_exp = tk.StringVar(value="0")
        self.session_time = tk.StringVar(value="-")
        self.session_rate = tk.StringVar(value="0")
        self.level_eta = tk.StringVar(value="-")
        self.status = tk.StringVar(value=STATUS_TEXT[LocatorState.SEARCHING])
        self.status_detail = tk.StringVar(value="")

        self.window = ExpRateWindow(
            root,
            current_vars=self.current_vars,
            current_exp=self.current_exp,
            current_percent=self.current_percent,
            session_exp=self.session_exp,
            session_time=self.session_time,
            session_rate=self.session_rate,
            level_eta=self.level_eta,
            status=self.status,
            status_detail=self.status_detail,
            on_clear_current=self.clear_current,
            on_clear_session=self.clear_session,
            on_retry=self.retry,
            on_float=self.enter_float,
        )
        self.retry_btn = self.window.retry_row.button
        self.status_label = self.window.info_section.status_label
        self.gain_chart = self.window.chart_section.gain_chart
        self.total_chart = self.window.chart_section.total_chart

        self._restore_position()
        self.root.after_idle(self._mark_window_placed)
        self.root.bind("<Configure>", self._on_root_configure)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        now = time.time()
        self._refresh_rates(now)
        self._redraw_chart(now)
        self._scan_due_at = now + 0.2
        self._refresh_status()
        self._tick_job = self.root.after(200, self.tick)
        self._ui_job = self.root.after(1000, self._ui_tick)

    def enter_float(self) -> None:
        if self._float is not None:
            return
        self.root.update_idletasks()
        x, y = self.root.winfo_x(), self.root.winfo_y()
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
        if self._float is not None:
            pos = self._float.position()
            overlay = self._float
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
        now = time.time()
        self._refresh_rates(now)
        self._redraw_chart(now)

    def clear_session(self) -> None:
        self.session.clear()
        self._refresh_rates(time.time())
        self._redraw_chart(time.time())

    def _status_detail(self, now: float | None = None) -> str:
        state = self.locator.state
        if state not in (LocatorState.SEARCHING, LocatorState.RELOCATING):
            return ""
        if now is None:
            now = time.time()
        left = max(0, math.ceil(self._scan_due_at - now))
        retries = min(self.locator.search_misses, Locator.SEARCH_FAIL_LIMIT)
        return f"({retries}/{Locator.SEARCH_FAIL_LIMIT}, {left}s)"

    def _scan_delay_ms(self) -> int:
        if self.locator.state == LocatorState.LOCKED:
            return LOCK_SCAN_MS
        return SEARCH_SCAN_MS

    def _refresh_status(self) -> None:
        state = self.locator.state
        self.status.set(STATUS_TEXT[state])
        self.status_detail.set(self._status_detail())
        self.status_label.configure(foreground=STATUS_COLOR[state])
        if state == LocatorState.FAILED:
            self.retry_btn.configure(state="normal")
        else:
            self.retry_btn.configure(state="disabled")
        self.window.info_section.set_preview_visible(state == LocatorState.LOCKED)

    def _apply_column(self, vars_map: dict[str, tk.StringVar], rates: Rates) -> None:
        vars_map["per_sec"].set(_fmt(rates.per_sec))
        vars_map["per_min"].set(_fmt(rates.per_min))
        vars_map["per_5min"].set(_fmt(rates.per_5min))
        vars_map["per_hour"].set(_fmt(rates.per_hour))

    def _refresh_rates(self, now: float) -> None:
        self._apply_column(self.current_vars, self.current.hourly_rates(now))
        if self.current.last_exp is None:
            self._accepted_percent = None
        self.current_exp.set(_fmt(self.current.last_exp))
        self.current_percent.set(_fmt_percent(self._accepted_percent))
        self.session_exp.set(_fmt(self.session.total_gained()))
        self.session_rate.set(_fmt(self.session.hourly_rates(now).per_hour))
        self.session_time.set(_fmt_duration(self.session.elapsed_since_first_gain(now)))
        eta = eta_to_level(
            self.current.last_exp,
            self._accepted_percent,
            self.current.total_gained(),
            self.current.elapsed_since_first_gain(now),
        )
        self.level_eta.set(_fmt_duration(eta))

    def _ui_tick(self) -> None:
        if self._closed or not self.root.winfo_exists():
            return
        now = time.time()
        self.current.clear_if_idle(now)
        self._refresh_rates(now)
        self._redraw_chart(now)
        if self.locator.state in (LocatorState.SEARCHING, LocatorState.RELOCATING):
            self._refresh_status()
        self._ui_job = self.root.after(1000, self._ui_tick)

    def tick(self) -> None:
        if self._closed or not self.root.winfo_exists():
            return
        if self._busy:
            delay = self._scan_delay_ms()
            self._scan_due_at = time.time() + delay / 1000
            self._tick_job = self.root.after(delay, self.tick)
            return
        self._busy = True
        try:
            self._scan_once()
        except Exception:
            pass
        finally:
            self._busy = False
            if self._closed or not self.root.winfo_exists():
                return
            delay = self._scan_delay_ms()
            self._scan_due_at = time.time() + delay / 1000
            self._refresh_status()
            self._tick_job = self.root.after(delay, self.tick)

    def _scan_once(self) -> None:
        now = time.time()
        if self.locator.state == LocatorState.FAILED:
            self._refresh_rates(now)
            return

        if self.locator.state in (LocatorState.SEARCHING, LocatorState.RELOCATING):
            self.window.info_section.set_preview_visible(False)
            self.root.update_idletasks()
            virtual_ocr, monitor_index = search_exp_label(
                last_rect=self.locator.last_rect,
                last_monitor_index=self.locator.last_monitor_index,
            )
            self.locator.on_search_result(virtual_ocr, monitor_index)
            if self.locator.state == LocatorState.LOCKED and virtual_ocr is not None:
                self._consume_crop(grab_region(*virtual_ocr), now)
            else:
                self._refresh_rates(now)
            return

        if self.locator.state == LocatorState.LOCKED and self.locator.locked_rect is not None:
            crop = grab_region(*self.locator.locked_rect)
            found = label_present(crop)
            self.locator.on_lock_check(found)
            if found:
                self._consume_crop(crop, now)
            else:
                self._refresh_rates(now)

    def _accept_percent(self, reading: ExpReading | None) -> None:
        if reading is None or reading.exp != self.current.last_exp:
            return
        self._accepted_percent = reading.percent

    def _consume_crop(self, crop, now: float) -> None:
        self._update_preview(crop)
        reading = read_exp_reading_from_bgr(crop)
        exp = None if reading is None else reading.exp
        self.current.tick(exp, now)
        self.session.tick(exp, now)
        self._accept_percent(reading)
        self._refresh_rates(now)

    def _update_preview(self, crop_bgr) -> None:
        if crop_bgr is None or crop_bgr.size == 0:
            return
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        slot = self.window.info_section.image_canvas
        r, g, b = slot.winfo_rgb(slot.cget("bg"))
        image = fit_image(
            Image.fromarray(rgb),
            Spacing.Info.preview_width,
            Spacing.Info.preview_height,
            fill=(r // 256, g // 256, b // 256),
        )
        photo = ImageTk.PhotoImage(image)
        self.window.info_section.set_image(photo)

    def _redraw_chart(self, now: float) -> None:
        trackers = {"current": self.current, "session": self.session}
        gain_spec, total_spec = CHARTS
        gain = trackers[gain_spec.source].chart_series(now, gain_spec)
        total = trackers[total_spec.source].chart_series(now, total_spec)
        gain_key = (tuple(gain), gain_spec.axis_start, gain_spec.suffix)
        total_key = (tuple(total), total_spec.axis_start, total_spec.suffix)
        if gain_key != self._last_gain_series:
            self._last_gain_series = gain_key
            paint_chart(
                self.gain_chart,
                gain,
                suffix=gain_spec.suffix,
                line=Type.Chart.gain_line,
                fill=Type.Chart.gain_fill,
                axis_start=gain_spec.axis_start,
            )
        if total_key != self._last_total_series:
            self._last_total_series = total_key
            paint_chart(
                self.total_chart,
                total,
                suffix=total_spec.suffix,
                line=Type.Chart.total_line,
                fill=Type.Chart.total_fill,
                axis_start=total_spec.axis_start,
            )


def _report_crash(exc: BaseException) -> None:
    import traceback

    log = data_dir() / "crash.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(traceback.format_exc(), encoding="utf-8")
    text = f"{exc}\n\n详情已写入:\n{log}"
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, "经验统计助手", 0x10)
    except Exception:
        pass


def main() -> None:
    try:
        warmup()
        root = tk.Tk()
        ExpRateApp(root)
        root.mainloop()
    except Exception as exc:
        _report_crash(exc)
        raise


if __name__ == "__main__":
    main()
