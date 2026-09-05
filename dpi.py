"""Keep the Tk window from resizing when dragged across DPI screens.

Per-monitor DPI on the UI thread makes Windows send WM_DPICHANGED whenever
the window sits on a 150% display (or whenever capture temporarily switches
the thread). Tk then rebuilds the layout: the window shrinks and flickers.

The process stays DPI-unaware. mss grabs that need physical pixels run on a
worker thread via physical_call. Graphics Capture runs on the caller thread.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes
from typing import TypeVar

_user32 = ctypes.windll.user32
_user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
_user32.SetProcessDpiAwarenessContext.restype = ctypes.c_int
_user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
_user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
_user32.LogicalToPhysicalPointForPerMonitorDPI.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.POINT),
]
_user32.LogicalToPhysicalPointForPerMonitorDPI.restype = wintypes.BOOL

_UNAWARE_GDISCALED = ctypes.c_void_p(-5)
_UNAWARE = ctypes.c_void_p(-1)
_PER_MONITOR_V2 = ctypes.c_void_p(-4)

_T = TypeVar("_T")
_call_lock = threading.Lock()


def disable_per_monitor_dpi() -> None:
    """Process stays DPI-unaware so the window size does not change per monitor."""
    try:
        if _user32.SetProcessDpiAwarenessContext(_UNAWARE_GDISCALED):
            return
        _user32.SetProcessDpiAwarenessContext(_UNAWARE)
    except Exception:
        pass


def logical_to_physical(hwnd: int, x: int, y: int) -> tuple[int, int]:
    point = wintypes.POINT(int(x), int(y))
    if not _user32.LogicalToPhysicalPointForPerMonitorDPI(hwnd, ctypes.byref(point)):
        return int(x), int(y)
    return int(point.x), int(point.y)


def dpi_scale(hwnd: int, x: int = 0, y: int = 0) -> float:
    """Physical pixels per logical pixel on the monitor that contains the window.

    Do not use LogicalToPhysicalPoint spanning 1000px: on a secondary display
    (negative virtual coords) that ratio comes back inverted (e.g. 0.245).
    GetDpiForWindow is 96 for a DPI-unaware HWND, so ask the monitor instead.
    """
    try:
        return physical_call(_dpi_for_window, hwnd, int(x), int(y))
    except Exception:
        return 1.0


def dpi_scale_at(x: int, y: int) -> float:
    """Physical pixels per logical pixel for the monitor containing a virtual-screen point."""
    try:
        return physical_call(_dpi_at_point, int(x), int(y))
    except Exception:
        return 1.0


def _dpi_at_point(x: int, y: int) -> float:
    _user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    _user32.MonitorFromPoint.restype = ctypes.c_void_p
    point = wintypes.POINT(int(x), int(y))
    scale = _monitor_dpi(int(_user32.MonitorFromPoint(point, 2)))
    return scale if scale > 0 else 1.0


def _monitor_dpi(monitor: int) -> float:
    if not monitor:
        return 0.0
    dpi_x = wintypes.UINT()
    dpi_y = wintypes.UINT()
    shcore = ctypes.windll.shcore
    shcore.GetDpiForMonitor.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(wintypes.UINT),
    ]
    shcore.GetDpiForMonitor.restype = ctypes.HRESULT
    status = shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
    if status == 0 and dpi_x.value:
        return dpi_x.value / 96.0
    return 0.0


def _dpi_for_window(hwnd: int, x: int = 0, y: int = 0) -> float:
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.MonitorFromWindow.restype = ctypes.c_void_p
    _user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    _user32.MonitorFromPoint.restype = ctypes.c_void_p
    scale = _monitor_dpi(int(_user32.MonitorFromWindow(hwnd, 2)))
    point = wintypes.POINT(int(x), int(y))
    point_scale = _monitor_dpi(int(_user32.MonitorFromPoint(point, 2)))
    if point_scale > scale + 0.02:
        scale = point_scale
    if scale > 0:
        return scale
    _user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    _user32.GetDpiForWindow.restype = wintypes.UINT
    dpi = int(_user32.GetDpiForWindow(hwnd))
    return dpi / 96.0 if dpi else 1.0


def physical_call(func: Callable[..., _T], *args: object) -> _T:
    """Run func on a worker that is per-monitor DPI aware. Does not touch the UI thread."""
    box: list[_T] = []
    error: list[BaseException] = []

    def worker() -> None:
        try:
            _user32.SetThreadDpiAwarenessContext(_PER_MONITOR_V2)
            box.append(func(*args))
        except BaseException as exc:
            error.append(exc)

    with _call_lock:
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join()
    if error:
        raise error[0]
    return box[0]
