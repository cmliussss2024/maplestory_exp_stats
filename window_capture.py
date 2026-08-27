"""Capture a window by HWND via Windows.Graphics.Capture."""

from __future__ import annotations

import ctypes
import time
from ctypes import HRESULT, POINTER, Structure, byref, c_int, c_uint, c_uint32, c_void_p, wintypes

import numpy as np


class GUID(Structure):
    _fields_ = [
        ("Data1", c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, text: str) -> None:
        parts = text.strip("{}").split("-")
        self.Data1 = int(parts[0], 16)
        self.Data2 = int(parts[1], 16)
        self.Data3 = int(parts[2], 16)
        self.Data4 = (ctypes.c_ubyte * 8).from_buffer_copy(bytes.fromhex(parts[3] + parts[4]))


class D3D11_TEXTURE2D_DESC(Structure):
    _fields_ = [
        ("Width", c_uint),
        ("Height", c_uint),
        ("MipLevels", c_uint),
        ("ArraySize", c_uint),
        ("Format", c_uint),
        ("SampleCount", c_uint),
        ("SampleQuality", c_uint),
        ("Usage", c_uint),
        ("BindFlags", c_uint),
        ("CPUAccessFlags", c_uint),
        ("MiscFlags", c_uint),
    ]


class D3D11_MAPPED_SUBRESOURCE(Structure):
    _fields_ = [
        ("pData", c_void_p),
        ("RowPitch", c_uint),
        ("DepthPitch", c_uint),
    ]


IID_IDXGIDevice2 = GUID("{05008617-FBFD-4051-A790-144884B4F6A9}")
IID_ID3D11Texture2D = GUID("{6f15aaf2-d208-4e89-9ab4-489535d34f9c}")
D3D11_SDK_VERSION = 7
D3D_DRIVER_TYPE_HARDWARE = 1
D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
D3D11_USAGE_STAGING = 3
D3D11_CPU_ACCESS_READ = 0x20000
D3D11_MAP_READ = 1
DXGI_FORMAT_B8G8R8A8_UNORM = 87

_device_native: int | None = None
_context_native: int | None = None
_winrt_device = None
_hwnd: int | None = None
_item = None
_pool = None
_session = None
_size: tuple[int, int] | None = None


def _vtbl(punk: int):
    return ctypes.cast(c_void_p(punk), POINTER(POINTER(c_void_p))).contents


def _qi(punk: int, iid: GUID) -> int:
    fn = ctypes.WINFUNCTYPE(c_int, c_void_p, POINTER(GUID), POINTER(c_void_p))(_vtbl(punk)[0])
    out = c_void_p()
    hr = fn(punk, byref(iid), byref(out))
    if hr != 0 or not out.value:
        raise OSError(f"QueryInterface failed hr=0x{hr & 0xFFFFFFFF:08X}")
    return int(out.value)


def _release(punk: int) -> None:
    fn = ctypes.WINFUNCTYPE(c_uint, c_void_p)(_vtbl(punk)[2])
    fn(punk)


def _ensure_d3d():
    global _device_native, _context_native, _winrt_device
    if _winrt_device is not None:
        return _device_native, _context_native, _winrt_device

    from winrt.windows.graphics.directx.direct3d11.interop import (
        create_direct3d11_device_from_dxgi_device,
    )

    device = c_void_p()
    context = c_void_p()
    hr = ctypes.windll.d3d11.D3D11CreateDevice(
        None,
        D3D_DRIVER_TYPE_HARDWARE,
        None,
        D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        None,
        0,
        D3D11_SDK_VERSION,
        byref(device),
        None,
        byref(context),
    )
    if hr != 0 or not device.value or not context.value:
        raise OSError(f"D3D11CreateDevice failed hr=0x{hr & 0xFFFFFFFF:08X}")
    dxgi = _qi(int(device.value), IID_IDXGIDevice2)
    _winrt_device = create_direct3d11_device_from_dxgi_device(dxgi)
    _release(dxgi)
    _device_native = int(device.value)
    _context_native = int(context.value)
    return _device_native, _context_native, _winrt_device


def _close_session() -> None:
    global _hwnd, _item, _pool, _session, _size
    for obj in (_session, _pool):
        if obj is None:
            continue
        try:
            obj.close()
        except Exception:
            pass
    _hwnd = None
    _item = None
    _pool = None
    _session = None
    _size = None


def _ensure_session(hwnd: int):
    from winrt.windows.graphics import SizeInt32
    from winrt.windows.graphics.capture import Direct3D11CaptureFramePool
    from winrt.windows.graphics.capture.interop import create_for_window
    from winrt.windows.graphics.directx import DirectXPixelFormat

    global _hwnd, _item, _pool, _session, _size
    _device, _context, winrt_device = _ensure_d3d()
    if _hwnd == hwnd and _session is not None and _pool is not None and _item is not None:
        size = (int(_item.size.width), int(_item.size.height))
        if size != _size and size[0] > 0 and size[1] > 0:
            _pool.recreate(
                winrt_device,
                DirectXPixelFormat.B8_G8_R8_A8_UINT_NORMALIZED,
                2,
                SizeInt32(size[0], size[1]),
            )
            _size = size
        return

    _close_session()
    item = create_for_window(hwnd)
    size = (int(item.size.width), int(item.size.height))
    if size[0] < 2 or size[1] < 2:
        raise OSError("capture item has empty size")
    pool = Direct3D11CaptureFramePool.create_free_threaded(
        winrt_device,
        DirectXPixelFormat.B8_G8_R8_A8_UINT_NORMALIZED,
        2,
        SizeInt32(size[0], size[1]),
    )
    session = pool.create_capture_session(item)
    try:
        session.is_border_required = False
    except Exception:
        pass
    try:
        session.is_cursor_capture_enabled = False
    except Exception:
        pass
    session.start_capture()
    _hwnd = hwnd
    _item = item
    _pool = pool
    _session = session
    _size = size


def _frame_to_bgr(frame) -> np.ndarray:
    from winrt.windows.graphics.directx.direct3d11.interop import get_dxgi_surface_from_object

    device, context, _winrt = _ensure_d3d()
    dxgi_surface = get_dxgi_surface_from_object(frame.surface)
    tex = _qi(int(dxgi_surface), IID_ID3D11Texture2D)
    _release(int(dxgi_surface))
    get_desc = ctypes.WINFUNCTYPE(None, c_void_p, POINTER(D3D11_TEXTURE2D_DESC))(_vtbl(tex)[10])
    desc = D3D11_TEXTURE2D_DESC()
    get_desc(tex, byref(desc))
    width, height = int(desc.Width), int(desc.Height)

    staging_desc = D3D11_TEXTURE2D_DESC()
    staging_desc.Width = width
    staging_desc.Height = height
    staging_desc.MipLevels = 1
    staging_desc.ArraySize = 1
    staging_desc.Format = DXGI_FORMAT_B8G8R8A8_UNORM
    staging_desc.SampleCount = 1
    staging_desc.Usage = D3D11_USAGE_STAGING
    staging_desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ
    staging = c_void_p()
    create_tex = ctypes.WINFUNCTYPE(
        HRESULT, c_void_p, POINTER(D3D11_TEXTURE2D_DESC), c_void_p, POINTER(c_void_p)
    )(_vtbl(device)[5])
    hr = create_tex(device, byref(staging_desc), None, byref(staging))
    if hr != 0 or not staging.value:
        _release(tex)
        raise OSError(f"CreateTexture2D failed hr=0x{hr & 0xFFFFFFFF:08X}")
    copy_res = ctypes.WINFUNCTYPE(None, c_void_p, c_void_p, c_void_p)(_vtbl(context)[47])
    copy_res(context, staging, tex)
    mapped = D3D11_MAPPED_SUBRESOURCE()
    map_fn = ctypes.WINFUNCTYPE(
        HRESULT, c_void_p, c_void_p, c_uint, c_uint, c_uint, POINTER(D3D11_MAPPED_SUBRESOURCE)
    )(_vtbl(context)[14])
    hr = map_fn(context, staging, 0, D3D11_MAP_READ, 0, byref(mapped))
    if hr != 0:
        _release(int(staging.value))
        _release(tex)
        raise OSError(f"Map failed hr=0x{hr & 0xFFFFFFFF:08X}")
    pitch = int(mapped.RowPitch)
    src = ctypes.cast(mapped.pData, POINTER(ctypes.c_ubyte * (pitch * height))).contents
    raw = np.frombuffer(src, dtype=np.uint8).reshape(height, pitch)
    bgra = np.ascontiguousarray(raw[:, : width * 4]).reshape(height, width, 4)
    bgr = bgra[:, :, :3].copy()
    unmap = ctypes.WINFUNCTYPE(None, c_void_p, c_void_p, c_uint)(_vtbl(context)[15])
    unmap(context, staging, 0)
    _release(int(staging.value))
    _release(tex)
    return bgr


def grab_hwnd(hwnd: int) -> np.ndarray | None:
    """Return a BGR frame of the window, or None if capture is unavailable."""
    try:
        _ensure_session(hwnd)
        assert _pool is not None
        frame = None
        for _ in range(30):
            frame = _pool.try_get_next_frame()
            if frame is not None:
                break
            time.sleep(0.02)
        if frame is None:
            return None
        try:
            return _frame_to_bgr(frame)
        finally:
            frame.close()
    except Exception:
        _close_session()
        return None


def client_origin(hwnd: int) -> tuple[int, int]:
    from dpi import logical_to_physical

    point = wintypes.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(hwnd, byref(point))
    return logical_to_physical(hwnd, int(point.x), int(point.y))
