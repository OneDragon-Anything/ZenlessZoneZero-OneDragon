# -*- mode: python ; coding: utf-8 -*-

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyInstaller.building.build_main import Analysis
    from PyInstaller.building.api import COLLECT, EXE, PYZ


a = Analysis(
    ['..\\src\\zzz_od\\win_exe\\launcher.py', 'freeze_seed.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['_cffi_backend'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook_path_inject.py'],
    excludes=['one_dragon', 'one_dragon.*', 'one_dragon_qt', 'one_dragon_qt.*', 'onnxocr', 'zzz_od', 'zzz_od.*'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OneDragon-Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
    icon=['..\\assets\\ui\\logo.ico'],
    contents_directory='.runtime',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OneDragon-Launcher',
)
