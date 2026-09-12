"""Window spacing and type styles.

Fonts and spacing are theme-independent. Color attributes (``Type.divider``,
``*_color``, status and chart colors) are backed by descriptors that resolve
against the active theme palette at access time, so they always reflect the
current theme even though callers read them through the class object.
"""

from __future__ import annotations

from dataclasses import dataclass

from ui.theme import palette

_FAMILY = "Microsoft YaHei UI"


class _PaletteColor:
    """Descriptor resolving a palette field for class- and instance reads."""

    def __init__(self, key: str) -> None:
        self._key = key

    def __get__(self, _obj, _objtype=None) -> str:
        return getattr(palette(), self._key)


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

    class Info:
        cell_spacing = 4
        retry_preview_spacing = 8
        # Logical 100% EXP crop is 172x37; keep the 242x68 preview slot (fits the 340px window).
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
    """Light-theme literals kept for compatibility (no longer referenced by UI)."""

    primary = "#101010"
    secondary = "#606060"
    tertiary = "#9D9D9D"


class Type:
    family = _FAMILY

    divider = _PaletteColor("divider")

    class Rate:
        header = (_FAMILY, 13, "bold")
        header_color = _PaletteColor("text_primary")
        hint = (_FAMILY, 9)
        hint_color = _PaletteColor("text_tertiary")
        caption = (_FAMILY, 10)
        caption_color = _PaletteColor("text_secondary")
        value = (_FAMILY, 15, "bold")
        value_color = _PaletteColor("text_primary")
        unit = (_FAMILY, 10)
        unit_color = _PaletteColor("text_tertiary")

    class Cumulative:
        caption = (_FAMILY, 10)
        caption_color = _PaletteColor("text_primary")
        value = (_FAMILY, 13, "bold")
        value_color = _PaletteColor("text_primary")
        unit = (_FAMILY, 10)
        unit_color = _PaletteColor("text_tertiary")

    class Info:
        label = (_FAMILY, 10)
        label_color = _PaletteColor("text_primary")
        value = (_FAMILY, 13, "bold")
        value_color = _PaletteColor("text_primary")
        detail = (_FAMILY, 10)
        detail_color = _PaletteColor("text_tertiary")
        status_ok = _PaletteColor("status_ok")
        status_search = _PaletteColor("status_search")
        status_error = _PaletteColor("status_error")

    class Chart:
        title = (_FAMILY, 10)
        title_color = _PaletteColor("text_primary")
        caption = (_FAMILY, 8)
        peak = _PaletteColor("text_secondary")
        axis = _PaletteColor("text_tertiary")
        canvas_bg = _PaletteColor("chart_bg")
        canvas_border = _PaletteColor("chart_border")
        grid = _PaletteColor("grid")
        gain_line = _PaletteColor("gain_line")
        gain_fill = _PaletteColor("gain_fill")
        total_line = _PaletteColor("total_line")
        total_fill = _PaletteColor("total_fill")

    class Overlay:
        hover_bg = "#222222"
        text = "#ffffff"
        unit = "#ffffff"
        shadow = "#000000"
        icon = "#ffffff"
