# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

import rapidocr_onnxruntime
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)
OCR_ROOT = Path(rapidocr_onnxruntime.__file__).resolve().parent

datas = [(str(ROOT / "assets" / "exp_label.png"), "assets")]
binaries = []
hiddenimports = [
    "ch_ppocr_v2_cls",
    "ch_ppocr_v2_cls.text_cls",
    "ch_ppocr_v2_cls.utils",
    "ch_ppocr_v3_det",
    "ch_ppocr_v3_det.text_detect",
    "ch_ppocr_v3_det.utils",
    "ch_ppocr_v3_rec",
    "ch_ppocr_v3_rec.text_recognize",
    "ch_ppocr_v3_rec.utils",
    "pyclipper",
    "shapely",
    "shapely.geometry",
    "yaml",
    "winrt.runtime",
    "winrt.windows.foundation",
    "winrt.windows.graphics",
    "winrt.windows.graphics.capture",
    "winrt.windows.graphics.capture.interop",
    "winrt.windows.graphics.directx",
    "winrt.windows.graphics.directx.direct3d11",
    "winrt.windows.graphics.directx.direct3d11.interop",
]

for package in (
    "rapidocr_onnxruntime",
    "onnxruntime",
    "cv2",
    "winrt",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(OCR_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "pack" / "pyi_rth_rapidocr.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mses",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MapleStoryExpStats",
)
