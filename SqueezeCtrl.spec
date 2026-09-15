# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the Windows executable.

Run with: uv run pyinstaller SqueezeCtrl.spec
"""

from PyInstaller.utils.hooks import collect_submodules

# pyvisa resolves the "@py" backend via a dynamically built module name
# (import_module("pyvisa_" + "py")), which PyInstaller's static import
# analysis can't follow on its own — so pyvisa_py and its submodules
# (serial/usb/tcpip/gpib session backends) have to be listed explicitly.
hiddenimports = collect_submodules("pyvisa_py")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SqueezeCtrl",
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
)
