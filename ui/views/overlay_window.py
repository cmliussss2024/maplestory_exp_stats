"""Transparent always-on-top HUD for current rates."""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from pathlib import Path

import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ui.layered import blit_layered, enable_layered, hwnd_of
from ui.styles import Spacing, Type
from dpi import dpi_scale

_ROWS = (
    ("per_sec", "/秒"),
    ("per_5min", "/5分"),
    ("per_hour", "/时"),
)

_WIN_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def _rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _load_font(size: int, *, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ("msyhbd.ttc", "msyh.ttc", "simhei.ttf") if bold else ("msyh.ttc", "msyhbd.ttc", "simhei.ttf")
    for name in names:
        path = _WIN_FONTS / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


_RESTORE = "还原"


def _draw_resize_handle(
    draw: ImageDraw.ImageDraw,
    x2: int,
    y2: int,
    size: int,
    color: tuple[int, int, int, int],
    width: int,
) -> None:
    step = max(3, size // 5)
    for index in range(3):
        inset = step + index * step
        draw.line(
            (x2 - inset, y2 - 3, x2 - 3, y2 - inset),
            fill=color,
            width=width,
        )


class OverlayWindow:
    def __init__(
        self,
        master: tk.Tk,
        *,
        vars_map: dict[str, tk.StringVar],
        on_restore: Callable[[], None],
        x: int,
        y: int,
        scale: float = 1.0,
    ) -> None:
        self._on_restore = on_restore
        self._vars = vars_map
        self._drag: tuple[int, int] | None = None
        self._resize: tuple[float, float, float, float, float] | None = None
        self._closed = False
        self._hover = False
        self._blitting = False
        self._x = x
        self._y = y
        self._scale = self._clamp_scale(scale)
        self._image: Image.Image | None = None
        self._restore_box: tuple[int, int, int, int] | None = None
        self._resize_box: tuple[int, int, int, int] | None = None
        self._traces: list[tuple[tk.StringVar, str]] = []
        self._fonts: dict[tuple[int, bool], ImageFont.ImageFont] = {}
        self._hwnd: int | None = None
        self._last_blit_key: tuple[int, int, int, int] | None = None
        self._input_dpi = 1.0

        win = tk.Toplevel(master)
        self._win = win
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.bind("<Enter>", lambda _event: self._set_hover(True))
        win.bind("<Leave>", self._on_leave)
        win.bind("<Motion>", self._on_motion)
        win.bind("<Button-1>", self._on_press)
        win.bind("<B1-Motion>", self._on_drag)
        win.bind("<ButtonRelease-1>", self._on_release)
        win.bind("<Configure>", self._on_configure)
        win.bind("<Expose>", self._on_expose)
        win.bind("<Destroy>", self._on_destroyed)

        for key, _unit in _ROWS:
            trace_id = vars_map[key].trace_add("write", self._on_var)
            self._traces.append((vars_map[key], trace_id))

        self._redraw("init")
        win.deiconify()
        win.update_idletasks()
        self._hwnd = hwnd_of(win)
        enable_layered(self._hwnd)
        self._refresh_input_dpi()
        self._blit("mapped")
        win.lift()

    @property
    def scale(self) -> float:
        return self._scale

    def position(self) -> tuple[int, int]:
        return (self._x, self._y)

    def destroy(self) -> None:
        self._closed = True
        for var, trace_id in self._traces:
            var.trace_remove("write", trace_id)
        self._traces.clear()
        if self._win.winfo_exists():
            self._win.destroy()

    def _clamp_scale(self, scale: float) -> float:
        return min(Spacing.Overlay.scale_max, max(Spacing.Overlay.scale_min, scale))

    def _px(self, value: float, *, minimum: int = 1) -> int:
        return max(minimum, round(value * self._scale))

    def _panel_margin(self) -> int:
        return Spacing.Overlay.shadow_blur * 2

    def _refresh_input_dpi(self) -> None:
        if self._hwnd is None:
            return
        scale = dpi_scale(self._hwnd, self._x, self._y)
        self._input_dpi = scale if scale > 0 else 1.0

    def _sync_tk_geom(self) -> None:
        if self._image is None or not self._win.winfo_exists():
            return
        width, height = self._image.size
        self._blitting = True
        self._win.geometry(f"{width}x{height}+{self._x}+{self._y}")
        self._win.update_idletasks()
        self._blitting = False

    def _font(self, size: int, *, bold: bool) -> ImageFont.ImageFont:
        key = (size, bold)
        cached = self._fonts.get(key)
        if cached is None:
            cached = _load_font(size, bold=bold)
            self._fonts[key] = cached
        return cached

    def _on_var(self, *_args: object) -> None:
        if self._closed or not self._win.winfo_exists():
            return
        if self._drag is not None or self._resize is not None:
            return
        self._redraw("var")

    def _set_hover(self, hovered: bool) -> None:
        if self._hover == hovered:
            return
        self._hover = hovered
        if hovered:
            self._refresh_input_dpi()
        self._redraw("hover")

    def _pointer_inside(self) -> bool:
        px, py = self._win.winfo_pointerxy()
        x = self._win.winfo_rootx()
        y = self._win.winfo_rooty()
        return x <= px < x + self._win.winfo_width() and y <= py < y + self._win.winfo_height()

    def _image_xy(self, event: tk.Event) -> tuple[float, float]:
        # Layered blit is 1:1 physical pixels. Tk mouse events on a
        # DPI-unaware process are logical (1.5x screen → coords are 2/3 of
        # the pixel the user actually clicked). Scale into image space.
        x = float(event.x_root - self._win.winfo_rootx()) * self._input_dpi
        y = float(event.y_root - self._win.winfo_rooty()) * self._input_dpi
        if self._image is None:
            return x, y
        win_w = max(1, self._win.winfo_width())
        win_h = max(1, self._win.winfo_height())
        img_w, img_h = self._image.size
        if abs(win_w - img_w) > 1 or abs(win_h - img_h) > 1:
            x = x * img_w / win_w
            y = y * img_h / win_h
        return x, y

    def _in_box(self, event: tk.Event, box: tuple[int, int, int, int] | None) -> bool:
        if box is None:
            return False
        x, y = self._image_xy(event)
        if self._image is not None:
            x = min(max(x, 0.0), float(self._image.width - 1))
            y = min(max(y, 0.0), float(self._image.height - 1))
        x1, y1, x2, y2 = box
        return x1 <= x <= x2 and y1 <= y <= y2

    def _on_leave(self, _event: tk.Event) -> None:
        if self._drag is not None or self._resize is not None:
            return
        if self._pointer_inside():
            return
        self._set_hover(False)

    def _on_motion(self, event: tk.Event) -> None:
        if self._in_box(event, self._restore_box):
            self._win.configure(cursor="hand2")
        elif self._in_box(event, self._resize_box) or self._resize is not None:
            self._win.configure(cursor="size_nw_se")
        else:
            self._win.configure(cursor="fleur")

    def _on_destroyed(self, event: tk.Event) -> None:
        if event.widget is not self._win or self._closed:
            return
        self._on_restore()

    def _on_press(self, event: tk.Event) -> None:
        self._refresh_input_dpi()
        self._set_hover(True)
        if self._in_box(event, self._restore_box):
            self._drag = None
            self._resize = None
            self._on_restore()
            return
        if self._in_box(event, self._resize_box):
            self._drag = None
            margin = self._panel_margin()
            origin_x = self._x + margin
            origin_y = self._y + margin
            self._resize = (
                origin_x,
                origin_y,
                event.x_root - origin_x,
                event.y_root - origin_y,
                self._scale,
            )
            return
        self._resize = None
        self._drag = (event.x_root - self._x, event.y_root - self._y)

    def _on_drag(self, event: tk.Event) -> None:
        if self._resize is not None:
            origin_x, origin_y, start_dx, start_dy, start_scale = self._resize
            dx = max(16.0, event.x_root - origin_x)
            dy = max(16.0, event.y_root - origin_y)
            start = math.hypot(max(16.0, start_dx), max(16.0, start_dy))
            scale = self._clamp_scale(start_scale * math.hypot(dx, dy) / start)
            if abs(scale - self._scale) < 0.001:
                return
            self._scale = scale
            self._redraw("resize")
            return
        if self._drag is None:
            return
        self._x = event.x_root - self._drag[0]
        self._y = event.y_root - self._drag[1]
        self._blitting = True
        self._win.geometry(f"+{self._x}+{self._y}")
        self._blitting = False

    def _on_release(self, _event: tk.Event) -> None:
        was_resize = self._resize is not None
        self._drag = None
        self._resize = None
        self._refresh_input_dpi()
        if was_resize:
            quantized = round(self._scale, 2)
            if quantized != self._scale:
                self._scale = quantized
            self._redraw("resize_end")
        if not self._pointer_inside():
            self._set_hover(False)

    def _on_configure(self, event: tk.Event) -> None:
        if event.widget is not self._win:
            return
        if self._blitting or self._drag is not None or self._resize is not None:
            return
        self._blit("configure")

    def _on_expose(self, event: tk.Event) -> None:
        if event.widget is not self._win:
            return
        if self._blitting or self._drag is not None or self._resize is not None:
            return
        self._blit("expose")

    def _blit(self, why: str = "blit") -> None:
        if self._closed or self._image is None or not self._win.winfo_exists():
            return
        hwnd = self._hwnd
        if hwnd is None:
            return
        image = self._image
        key = (*image.size, self._x, self._y)
        last = self._last_blit_key
        if why in {"configure", "expose", "var"} and key == last:
            return
        self._last_blit_key = key
        blit_layered(hwnd, image)

    def _redraw(self, why: str = "redraw") -> None:
        if self._closed or not self._win.winfo_exists():
            return
        before = None if self._image is None else self._image.size
        self._image = self._render()
        width, height = self._image.size
        if self._resize is None:
            if why == "var" and before == (width, height):
                self._blit(why)
                return
            self._sync_tk_geom()
        self._blit(why)

    def _render(self) -> Image.Image:
        pad_x = self._px(Spacing.Overlay.pad_x)
        pad_y = self._px(Spacing.Overlay.pad_y)
        gap = self._px(Spacing.Overlay.value_unit_gap)
        row_gap = self._px(Spacing.Overlay.row_gap)
        handle = self._px(Spacing.Overlay.handle_size, minimum=14)
        label_gap = self._px(12)
        stroke = self._px(2)
        blur = Spacing.Overlay.shadow_blur
        offset = Spacing.Overlay.shadow_offset
        radius = self._px(Spacing.Overlay.radius, minimum=4)
        margin = blur * 2
        value_font = self._font(self._px(Spacing.Overlay.value_size, minimum=12), bold=True)
        unit_font = self._font(self._px(Spacing.Overlay.unit_size, minimum=8), bold=False)
        restore_font = unit_font
        fill = (*_rgb(Type.Overlay.text), 255)
        unit_fill = (*_rgb(Type.Overlay.unit), 255)
        shadow = (*_rgb(Type.Overlay.shadow), Spacing.Overlay.shadow_alpha)
        hover_fill = (*_rgb(Type.Overlay.hover_bg), Spacing.Overlay.hover_alpha)
        icon_fill = (*_rgb(Type.Overlay.icon), 255)
        restore_w = int(restore_font.getlength(_RESTORE))
        _rx0, r_top, _rx1, r_bottom = restore_font.getbbox(_RESTORE, anchor="ls")

        lines: list[tuple[str, str, float]] = []
        max_ascent = 0
        max_descent = 0
        text_w = 0
        for key, unit in _ROWS:
            value = self._vars[key].get()
            _vx0, vy0, _vx1, vy1 = value_font.getbbox(value, anchor="ls")
            _ux0, uy0, _ux1, uy1 = unit_font.getbbox(unit, anchor="ls")
            value_w = value_font.getlength(value)
            unit_w = unit_font.getlength(unit)
            max_ascent = max(max_ascent, -vy0, -uy0)
            max_descent = max(max_descent, vy1, uy1)
            text_w = max(text_w, int(value_w + gap + unit_w))
            lines.append((value, unit, value_w))

        line_h = max_ascent + max_descent
        text_h = line_h * len(lines) + row_gap * (len(lines) - 1)
        inner_w = pad_x * 2 + text_w + label_gap + restore_w
        inner_h = pad_y * 2 + text_h
        width = inner_w + margin * 2
        height = inner_h + margin * 2
        origin_x = margin + pad_x
        origin_y = margin + pad_y
        panel = (margin, margin, width - margin - 1, height - margin - 1)

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        grip = max(handle, self._px(36, minimum=32))
        gx2 = width - 1
        gy2 = height - 1
        gx1 = max(0, panel[2] + 1 - grip)
        gy1 = max(0, panel[3] + 1 - grip)
        if self._hover:
            # ULW_ALPHA ignores alpha=0, so the rounded SE corner (where the
            # handle is drawn) would otherwise click through. Keep every hover
            # pixel hittable, and fill the grip square so the cutout is solid.
            hover = Image.new("RGBA", (width, height), (0, 0, 0, 1))
            hover_draw = ImageDraw.Draw(hover)
            hover_draw.rounded_rectangle(panel, radius=radius, fill=hover_fill)
            hover_draw.rectangle((gx1, gy1, gx2, gy2), fill=hover_fill)
            image = Image.alpha_composite(image, hover)

        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)

        y = origin_y
        for value, unit, value_w in lines:
            baseline = y + max_ascent
            unit_x = origin_x + value_w + gap
            shadow_draw.text(
                (origin_x + offset, baseline + offset),
                value,
                font=value_font,
                fill=shadow,
                anchor="ls",
            )
            shadow_draw.text(
                (unit_x + offset, baseline + offset),
                unit,
                font=unit_font,
                fill=shadow,
                anchor="ls",
            )
            text_draw.text(
                (origin_x, baseline),
                value,
                font=value_font,
                fill=fill,
                anchor="ls",
            )
            text_draw.text(
                (unit_x, baseline),
                unit,
                font=unit_font,
                fill=unit_fill,
                anchor="ls",
            )
            y += line_h + row_gap

        if blur:
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
        image = Image.alpha_composite(image, shadow_layer)
        image = Image.alpha_composite(image, text_layer)

        if self._hover:
            overlay = ImageDraw.Draw(image)
            baseline = origin_y + max_ascent
            right = width - margin - pad_x
            overlay.text(
                (right, baseline),
                _RESTORE,
                font=restore_font,
                fill=fill,
                anchor="rs",
            )
            hit_pad = self._px(8, minimum=6)
            self._restore_box = (
                int(right - restore_w - hit_pad),
                int(panel[1]),
                int(panel[2]),
                int(baseline + r_bottom + hit_pad),
            )
            _draw_resize_handle(overlay, panel[2], panel[3], handle, icon_fill, stroke)
            self._resize_box = (gx1, gy1, gx2, gy2)
        else:
            self._restore_box = None
            self._resize_box = None

        return image
