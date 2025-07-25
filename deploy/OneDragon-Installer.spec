# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['..\\src\\zzz_od\\gui\\zzz_installer.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../config/project.yml', 'resources/config'),
        ('../assets/text', 'resources/assets/text'),
        ('../assets/ui', 'resources/assets/ui')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OneDragon-Installer',
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
    uac_admin=False,
    icon=['..\\assets\\ui\\logo.ico'],
)
