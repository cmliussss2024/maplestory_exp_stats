"""Window spacing and type styles."""

from __future__ import annotations

from dataclasses import dataclass

_FAMILY = "Microsoft YaHei UI"


@dataclass(frozen=True)
class Padding:
    top: int
    right: int
    bottom: int
    left: int

    @property
    def padx(self) -> tuple[int, int]:
        return (self.left, self.right)

    @property
    def pady(self) -> tuple[int, int]:
        return (self.top, self.bottom)


class Spacing:
    window_width = 340
    section_padding = Padding(top=12, right=12, bottom=12, left=12)
    divider_width = 1

    class Rate:
        grid_col_gap = 12
        grid_row_gap = 0
        value_unit_gap = 0
        clear_pad_y = (4, 4)
        hint_pad_y = (0, 8)

    class Cumulative:
        cell_spacing = 2
        value_unit_gap = 4
        clear_pad_y = (4, 4)
        hint_pad_y = (0, 2)

    class Info:
        cell_spacing = 4
        retry_preview_spacing = 8
        # Logical 100% EXP crop is 121x34; keep the old 2x preview slot at all DPIs.
        preview_width = 242
        preview_height = 68

    class Chart:
        title_pad_bottom = 2
        gain_bottom_pad = 6
        total_bottom_pad = 0
        height = 118
        pad_x = 16
        pad_top = 22
        pad_bottom = 36
        caption_y = 10
        axis_label_y_offset = 14

    Chart.width = window_width - section_padding.left - section_padding.right

    class Overlay:
        pad_x = 10
        pad_y = 8
        row_gap = 2
        value_unit_gap = 8
        value_size = 28
        unit_size = 16
        shadow_offset = 2
        shadow_blur = 5
        shadow_alpha = 140
        hover_alpha = 150
        radius = 10
        handle_size = 18
        scale_min = 0.5
        scale_max = 3.0


class Color:
    primary = "#101010"
    secondary = "#606060"
    tertiary = "#9D9D9D"


class Type:
    family = _FAMILY
    divider = "#d9d9d9"

    class Rate:
        header = (_FAMILY, 13, "bold")
        header_color = Color.primary
        hint = (_FAMILY, 9)
        hint_color = Color.tertiary
        caption = (_FAMILY, 10)
        caption_color = Color.secondary
        value = (_FAMILY, 15, "bold")
        value_color = Color.primary
        unit = (_FAMILY, 10)
        unit_color = Color.tertiary

    class Cumulative:
        header = (_FAMILY, 13, "bold")
        header_color = Color.primary
        hint = (_FAMILY, 9)
        hint_color = Color.tertiary
        caption = (_FAMILY, 10)
        caption_color = Color.primary
        value = (_FAMILY, 13, "bold")
        value_color = Color.primary
        unit = (_FAMILY, 10)
        unit_color = Color.tertiary

    class Info:
        label = (_FAMILY, 10)
        label_color = Color.primary
        value = (_FAMILY, 13, "bold")
        value_color = Color.primary
        detail = (_FAMILY, 10)
        detail_color = Color.tertiary
        status_ok = "#2e7d32"
        status_search = "#e6a817"
        status_error = "#c62828"

    class Chart:
        title = (_FAMILY, 10)
        title_color = Color.primary
        caption = (_FAMILY, 8)
        peak = Color.secondary
        axis = Color.tertiary
        canvas_bg = "#f7f7f7"
        canvas_border = "#d0d0d0"
        grid = "#e6e6e6"
        gain_line = "#2e7d32"
        gain_fill = "#c8e6c9"
        total_line = "#1565c0"
        total_fill = "#bbdefb"

    class Overlay:
        hover_bg = "#222222"
        text = "#ffffff"
        unit = "#ffffff"
        shadow = "#000000"
        icon = "#ffffff"
