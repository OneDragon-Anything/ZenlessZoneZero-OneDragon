# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['..\\src\\zzz_od\\win_exe\\launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../config/project.yml', 'resources/config'),
        ('../config/repository.yml', 'resources/config'),
    ],
    hiddenimports=['_cffi_backend'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# 自解压期启动图：bootloader 在解压/提权重启期间显示，早于任何 Python 代码
splash = Splash(
    '..\\assets\\ui\\splash_f9.png',
    binaries=a.binaries,
    datas=a.datas,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    splash,
    splash.binaries,
    [],
    name='OneDragon-Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    # console 子系统保持 True（-v 的 stdout 会被其他程序读取，不能改 windowed）。
    # hide-early：双击启动（程序自有控制台）时由 bootloader 在解包最初隐藏黑窗——
    # onefile 解压数秒期间 Python 尚未运行，Python 层的 hide_console_window
    # 管不到这一段，只有该选项能覆盖；从终端启动不拥有控制台，不受影响。
    hide_console='hide-early',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
    icon=['..\\assets\\ui\\logo.ico'],
)
