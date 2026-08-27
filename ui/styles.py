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
    window_width = 372
    section_padding = Padding(top=16, right=16, bottom=16, left=16)
    rate_cell_spacing = 2
    forecast_value_unit_gap = 4
    session_value_unit_gap = 4
    forecast_clear_pad_y = (4, 4)
    session_clear_pad_y = (4, 4)
    divider_width = 1
    info_cell_spacing = 4
    retry_preview_spacing = 8
    tab_bar_height = 32
    tab_radius = 10
    tab_inset = 1
    chart_title_pad_bottom = 2
    gain_chart_bottom_pad = 6
    total_chart_bottom_pad = 0
    chart_height = 118
    chart_pad_x = 16
    chart_pad_top = 22
    chart_pad_bottom = 36
    chart_caption_y = 10
    chart_axis_label_y_offset = 14
    chart_width = window_width - section_padding.left - section_padding.right
    # Logical 100% EXP crop is 121x34; keep the old 2x preview slot at all DPIs.
    preview_width = 242
    preview_height = 68
    menu_bar_pad_x = 12
    menu_bar_pad_y = 4
    overlay_pad_x = 10
    overlay_pad_y = 8
    overlay_row_gap = 2
    overlay_value_unit_gap = 8
    overlay_value_size = 28
    overlay_unit_size = 16
    overlay_shadow_offset = 2
    overlay_shadow_blur = 5
    overlay_shadow_alpha = 140
    overlay_hover_alpha = 150
    overlay_radius = 10
    overlay_handle_size = 18
    overlay_scale_min = 0.5
    overlay_scale_max = 3.0


class Type:
    family = _FAMILY
    rate_header = (_FAMILY, 10)
    rate_header_color = "#000000"
    rate_value = (_FAMILY, 16, "bold")
    rate_value_color = "#000000"
    rate_unit = (_FAMILY, 10)
    rate_unit_color = "#888888"
    info_label = (_FAMILY, 10)
    info_label_color = "#000000"
    info_value = (_FAMILY, 16, "bold")
    info_value_color = "#000000"
    status_ok = "#000000"
    status_error = "#c62828"
    chart_title = (_FAMILY, 10)
    chart_title_color = "#000000"
    chart_caption = (_FAMILY, 8)
    chart_peak = "#666666"
    chart_axis = "#888888"
    tab = (_FAMILY, 9)
    tab_active = (_FAMILY, 9, "bold")
    tab_text = "#666666"
    tab_active_text = "#222222"
    divider = "#d9d9d9"
    tab_track = "#eaeaea"
    tab_active_bg = "#ffffff"
    tab_border = "#d9d9d9"
    chart_canvas_bg = "#f7f7f7"
    chart_canvas_border = "#d0d0d0"
    chart_grid = "#e6e6e6"
    gain_line = "#2e7d32"
    gain_fill = "#c8e6c9"
    total_line = "#1565c0"
    total_fill = "#bbdefb"
    overlay_hover_bg = "#222222"
    overlay_text = "#ffffff"
    overlay_unit = "#ffffff"
    overlay_shadow = "#000000"
    overlay_icon = "#ffffff"
