"""Current exp, session totals, status, retry, and crop preview."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import tkinter as tk

from ui.styles import Spacing
from ui.views.info.info_row_cell import InfoRowCell
from ui.views.info.retry_row_cell import RetryRowCell
from ui.views.section_panel import SectionPanel


class InfoSectionPanel(SectionPanel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        current_exp: tk.StringVar,
        current_percent: tk.StringVar,
        status: tk.StringVar,
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
            row = InfoRowCell(self.content, caption=caption, variable=var)
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
        self._photo: tk.PhotoImage | None = None
        self._image_id: int | None = None

    def set_preview_visible(self, visible: bool) -> None:
        mapped = bool(self.image_canvas.winfo_manager())
        if visible and not mapped:
            self.image_canvas.pack(pady=(Spacing.Info.retry_preview_spacing, 0))
        elif not visible and mapped:
            self.image_canvas.pack_forget()

    def set_image(self, photo: tk.PhotoImage) -> None:
        if self._image_id is None:
            self._image_id = self.image_canvas.create_image(
                Spacing.Info.preview_width // 2,
                Spacing.Info.preview_height // 2,
                image=photo,
                anchor="center",
            )
        else:
            self.image_canvas.itemconfigure(self._image_id, image=photo)
        self._photo = photo
