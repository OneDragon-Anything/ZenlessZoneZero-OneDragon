# -*- mode: python ; coding: utf-8 -*-


def _is_unneeded_binary(binary) -> bool:
    """过滤安装器用不到的 Qt DLL（widgets 渲染不需要 Qml/Quick/Pdf/OpenGL 软件渲染）。"""
    dest = str(binary[0]).lower().replace('\\', '/')
    unneeded = (
        'opengl32sw.dll',
        'qt6quick.dll', 'qt6qml.dll', 'qt6pdf.dll',
        'qt6qmlmodels.dll', 'qt6qmlmeta.dll', 'qt6qmlworkerscript.dll',
        'qt6virtualkeyboard.dll',
        'qtvirtualkeyboardplugin.dll', 'qtuiotouchplugin.dll',
        'qmlscenegraph.dll', 'quick3d.dll',
    )
    return any(dest.endswith(name) for name in unneeded)


a = Analysis(
    ['..\\src\\zzz_od\\gui\\zzz_installer.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../config/project.yml', 'resources/config'),
        ('../config/repository.yml', 'resources/config'),
        ('../assets/text', 'resources/assets/text'),
        # 安装器界面只用 logo.ico，主程序的背景/海报素材不打包
        ('../assets/ui/logo.ico', 'resources/assets/ui')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 主程序科学计算/音频/视觉库，安装器用不到
        'scipy', 'matplotlib', 'gensim', 'librosa',
        'numba', 'soundfile', 'sounddevice', 'soxr', 'audioread',
        'pandas', 'sklearn', 'sympy',
        'cv2', 'onnxruntime', 'onnxruntime_directml', 'shapely', 'pyclipper',
        # 开发/测试工具，运行时不需要
        'pytest', '_pytest', 'setuptools', 'wheel', 'pip',
        'pygments', 'pyreadline3', 'distutils',
        # 安装器用不到的 Qt 模块（qfluentwidgets 只需要 Widgets/Core/Gui/Svg）
        'PySide6.QtPdf', 'PySide6.QtQml', 'PySide6.QtQuick',
        'PySide6.QtVirtualKeyboard', 'PySide6.QtOpenGL',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.QtCharts',
        'PySide6.QtDataVisualization', 'PySide6.QtWebEngineCore',
    ],
    noarchive=False,
    optimize=0,
)
# excludes 只能排除 .pyd，Qt 的 .dll 由 PyInstaller hook 强制收集，需在 Analysis 后手动过滤
a.binaries = [b for b in a.binaries if not _is_unneeded_binary(b)]
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
