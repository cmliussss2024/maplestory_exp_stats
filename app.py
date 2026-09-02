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
from ui import theme
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
    read_exp_reading_from_bgr,
    to_virtual_rect,
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


def _status_color(state: LocatorState) -> str:
    """Resolve the status text color from the current theme at call time."""
    if state == LocatorState.LOCKED:
        return Type.Info.status_ok
    if state == LocatorState.FAILED:
        return Type.Info.status_error
    return Type.Info.status_search


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
        self.root.title("冒险岛经验统计助手")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.locator = Locator()
        self.current = RateTracker()
        self.session = RateTracker(history_path=HISTORY_PATH)
        self._busy = False
        self._closed = False
        self._last_exp: int | None = None
        self._last_percent: float | None = None
        self._eta_exp: int | None = None
        self._eta_percent: float | None = None
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
        self._preview_crop = None

        # Apply the persisted theme before any widget is created so the first
        # frame already uses the right palette.
        theme.set_theme(theme.load_preference())

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
            on_toggle_theme=self.on_toggle_theme,
        )
        self.retry_btn = self.window.retry_row.button
        self.status_label = self.window.info_section.status_label
        self.theme_button = self.window.theme_button
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
        now = time.time()
        self._refresh_rates(now)
        self._redraw_chart(now)

    def clear_session(self) -> None:
        self.session.clear()
        self._refresh_rates(time.time())
        self._redraw_chart(time.time())

    def on_toggle_theme(self) -> None:
        next_name = "dark" if theme.current_theme() == "light" else "light"
        self.apply_theme(next_name)

    def apply_theme(self, name: str) -> None:
        """Switch theme, persist it, then repaint colors/data-dependent parts."""
        if self._float is not None or self._closed:
            return
        theme.set_theme(name)
        theme.save_preference(name)
        self.window.apply_theme()
        self._refresh_status()
        self._redraw_chart(time.time(), force=True)
        if self._preview_crop is not None:
            self._update_preview(self._preview_crop)

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
        self.status_label.configure(foreground=_status_color(state))
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
        self.current_exp.set(_fmt(self._last_exp))
        self.current_percent.set(_fmt_percent(self._last_percent))
        self.session_exp.set(_fmt(self.session.total_gained()))
        self.session_rate.set(_fmt(self.session.hourly_rates(now).per_hour))
        self.session_time.set(_fmt_duration(self.session.elapsed_since_first_gain(now)))
        current_elapsed = self.current.elapsed_since_first_gain(now)
        eta = eta_to_level(
            self._eta_exp,
            self._eta_percent,
            self.current.total_gained(),
            current_elapsed,
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
        except Exception as exc:
            overlay_log("scan_error", error=repr(exc))
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
            self._set_live_reading(None)
            self._refresh_rates(now)
            return

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
            else:
                self._set_live_reading(None)
                self._refresh_rates(now)
            return

        if self.locator.state == LocatorState.LOCKED and self.locator.locked_rect is not None:
            crop = grab_region(*self.locator.locked_rect)
            found = label_present(crop)
            self.locator.on_lock_check(found)
            if found:
                self._consume_crop(crop, now)
            else:
                self._set_live_reading(None)
                self._refresh_rates(now)

    def _set_live_reading(self, reading: ExpReading | None) -> None:
        if reading is None:
            self._last_exp = None
            self._last_percent = None
            return
        self._last_exp = reading.exp
        self._last_percent = reading.percent
        self._eta_exp = reading.exp
        self._eta_percent = reading.percent

    def _consume_crop(self, crop, now: float) -> None:
        self._update_preview(crop)
        reading = read_exp_reading_from_bgr(crop)
        exp = None if reading is None else reading.exp
        self.current.tick(exp, now)
        self.session.tick(exp, now)
        self._set_live_reading(reading)
        self._refresh_rates(now)

    def _update_preview(self, crop_bgr) -> None:
        if crop_bgr is None or crop_bgr.size == 0:
            self._preview_crop = None
            return
        self._preview_crop = crop_bgr
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

    def _redraw_chart(self, now: float, *, force: bool = False) -> None:
        trackers = {"current": self.current, "session": self.session}
        gain_spec, total_spec = CHARTS
        gain = trackers[gain_spec.source].chart_series(now, gain_spec)
        total = trackers[total_spec.source].chart_series(now, total_spec)
        gain_key = (tuple(gain), gain_spec.axis_start, gain_spec.suffix)
        total_key = (tuple(total), total_spec.axis_start, total_spec.suffix)
        if force or gain_key != self._last_gain_series:
            self._last_gain_series = gain_key
            paint_chart(
                self.gain_chart,
                gain,
                suffix=gain_spec.suffix,
                line=Type.Chart.gain_line,
                fill=Type.Chart.gain_fill,
                axis_start=gain_spec.axis_start,
            )
        if force or total_key != self._last_total_series:
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

        ctypes.windll.user32.MessageBoxW(0, text, "冒险岛经验统计助手", 0x10)
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
