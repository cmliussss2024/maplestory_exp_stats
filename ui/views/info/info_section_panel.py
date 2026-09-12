"""Current exp, session totals, status, retry, and crop preview."""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import Any

import tkinter as tk

from PIL import ImageTk

from ui import theme
from ui.styles import Spacing
from ui.views.info.info_row_cell import InfoRowCell
from ui.views.info.retry_row_cell import RetryRowCell
from ui.views.section_panel import SectionPanel

# Tk's canvas takes any Tk image object, and Pillow's ``ImageTk.PhotoImage`` is a
# separate class from ``tkinter.PhotoImage`` (no inheritance), so allow both.
TkImage = tk.PhotoImage | ImageTk.PhotoImage


class InfoSectionPanel(SectionPanel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        current_exp: tk.StringVar,
        current_percent: tk.StringVar,
        status: tk.StringVar,
        status_detail: tk.StringVar,
        on_retry: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        rows = (
            ("状态", status),
            ("当前经验", current_exp),
            ("当前百分比", current_percent),
        )
        last = len(rows) - 1
        for index, (caption, var) in enumerate(rows):
            row = InfoRowCell(
                self.content,
                caption=caption,
                variable=var,
                detail=status_detail if caption == "状态" else None,
            )
            row.pack(fill="x", pady=(0, Spacing.Info.cell_spacing) if index < last else 0)
            if caption == "状态":
                self.status_label = row.value_label

        self.retry_row = RetryRowCell(self.content, on_retry=on_retry)
        self.retry_row.pack(fill="x", pady=(Spacing.Info.cell_spacing, 0))

        bg = str(self.content.cget("bg"))
        self.image_canvas = tk.Canvas(
            self.content,
            width=Spacing.Info.preview_width,
            height=Spacing.Info.preview_height,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self.image_canvas.pack(pady=(Spacing.Info.retry_preview_spacing, 0))
        self._photo: TkImage | None = None
        self._image_id: int | None = None
        self._preview_visible = False

    def set_preview_visible(self, visible: bool) -> None:
        self._preview_visible = visible
        if self._image_id is not None:
            self.image_canvas.itemconfigure(
                self._image_id,
                state="normal" if visible else "hidden",
            )

    def flush_hidden_preview(self, root: tk.Misc) -> None:
        """Hide the crop and pump paint so a desktop grab cannot see it."""
        self.set_preview_visible(False)
        self.image_canvas.update_idletasks()
        try:
            hwnd = int(self.image_canvas.winfo_id())
            user32 = ctypes.windll.user32
            user32.InvalidateRect(hwnd, None, True)
            user32.UpdateWindow(hwnd)
        except Exception:
            pass
        root.update()

    def set_image(self, photo: TkImage) -> None:
        state = "normal" if self._preview_visible else "hidden"
        if self._image_id is None:
            self._image_id = self.image_canvas.create_image(
                Spacing.Info.preview_width // 2,
                Spacing.Info.preview_height // 2,
                image=photo,
                anchor="center",
                state=state,
            )
        else:
            self.image_canvas.itemconfigure(
                self._image_id,
                image=photo,
                state=state,
            )
        self._photo = photo

    def _clear_preview(self) -> None:
        if self._image_id is not None:
            self.image_canvas.delete(self._image_id)
            self._image_id = None
        self._photo = None

    def apply_theme(self) -> None:
        super().apply_theme()
        # Repaint the slot background first; app repaints the crop on top so
        # the fitted image padding uses the new background color.
        self.image_canvas.configure(bg=theme.palette().bg)
        self._clear_preview()
