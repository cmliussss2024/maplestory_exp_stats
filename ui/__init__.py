"""UI package: styles, helpers, and view components."""

from ui.chart_view import CHART_LAYOUT, paint_chart
from ui.constants import WINDOW_PATH
from ui.debug import DEBUG_BG_ALPHA, DEBUG_PANELS
from ui.styles import Spacing, Type
from ui.views import (
    ChartCardPanel,
    ChartSectionPanel,
    ChartTabBarCell,
    ExpRateWindow,
    InfoSectionPanel,
    RateColumnPanel,
    RateSectionPanel,
    RetryRowCell,
    SectionPanel,
)

WINDOW_WIDTH = Spacing.window_width
CHART_MARGIN = Spacing.section_padding.left
CHART_WIDTH = Spacing.chart_width
H_MARGIN = Spacing.section_padding.left

__all__ = [
    "CHART_LAYOUT",
    "CHART_MARGIN",
    "CHART_WIDTH",
    "ChartCardPanel",
    "ChartSectionPanel",
    "ChartTabBarCell",
    "DEBUG_BG_ALPHA",
    "DEBUG_PANELS",
    "ExpRateWindow",
    "H_MARGIN",
    "InfoSectionPanel",
    "RateColumnPanel",
    "RateSectionPanel",
    "RetryRowCell",
    "SectionPanel",
    "Spacing",
    "Type",
    "WINDOW_PATH",
    "WINDOW_WIDTH",
    "paint_chart",
]
