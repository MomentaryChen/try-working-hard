# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file build for try-working-hard (run from project root: uv run pyinstaller packaging/try-working-hard.spec)."""
import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# PyInstaller 6+ may set SPECPATH to the spec file or its directory; parent of packaging/ = repo root
_sp = os.path.abspath(SPECPATH)
_spec_dir = _sp if os.path.isdir(_sp) else os.path.dirname(_sp)
_ROOT = os.path.normpath(os.path.join(_spec_dir, ".."))


datas: list = []
binaries: list = []
hiddenimports: list = []

for pkg in ("customtkinter", "pystray"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

try:
    datas += collect_data_files("mouse_jiggler")
except Exception:
    pass

hiddenimports += list(collect_submodules("mouse_jiggler"))


a = Analysis(
    [os.path.join(_ROOT, "mouse_jiggler", "__main__.py")],
    pathex=[_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

_ICO = os.path.join(_spec_dir, "app.ico")
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="try-working-hard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICO if os.path.isfile(_ICO) else None,
)
