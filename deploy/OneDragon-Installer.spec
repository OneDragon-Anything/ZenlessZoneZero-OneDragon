# -*- mode: python ; coding: utf-8 -*-

import os


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
    hiddenimports=[
        # pygit2 的 _libgit2.pyd 是 cffi ABI 编译的二进制，内部 import _cffi_backend，
        # PyInstaller 静态分析看不到，需显式收集
        'cffi', '_cffi_backend',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 主程序科学计算/音频/视觉库，安装器用不到
        'scipy', 'matplotlib', 'gensim', 'librosa',
        'numba', 'soundfile', 'sounddevice', 'soxr', 'audioread',
        'pandas', 'sklearn', 'sympy',
        'cv2', 'onnxruntime', 'onnxruntime_directml', 'shapely', 'pyclipper',
        # numpy 由 PIL.Image 惰性 import（仅 toarray 路径），安装器用不到；
        # cryptography 由 PyInstaller hooks-contrib 误收集，安装器 urllib 下载不依赖
        'numpy', 'cryptography', 'jwt', 'requests', 'urllib3',
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
def _is_unneeded_binary2(binary) -> bool:
    """过滤安装器用不到的二进制：numpy openblas、cryptography、PIL avif 插件。"""
    dest = str(binary[0]).lower().replace('\\', '/')
    unneeded = (
        # numpy/scipy 的 BLAS 与随机数库（安装器不用 numpy）
        'numpy.libs/libscipy_openblas', 'numpy.libs/msvcp140',
        'numpy/_core/', 'numpy/fft/', 'numpy/linalg/', 'numpy/random/',
        # cryptography 全家（其 DLL 在 cryptography/hazmat/ 子目录下，
        # 顶层 libssl/libcrypto 是 Python 标准库 _ssl 的依赖，不能按文件名过滤）
        'cryptography/hazmat/',
        # PIL 只用基础图像（_imaging），avif 插件 7.5MB 用不到
        'pil/_avif',
        # Qt 翻译文件只保留中英文，其余语言 qm 共约 2MB
        'translations/qt_',
    )
    # 只保留 zh_CN 和 en 的 Qt 翻译，其余语言砍掉
    if 'translations/qt_' in dest and not (
        dest.endswith('qt_zh_cn.qm') or dest.endswith('qt_en.qm')
    ):
        return True
    return any(name in dest for name in unneeded)


# Git 的 OpenSSL 3.5 与 Python 3.11 的 _ssl.pyd（链接 OpenSSL 3.0）不兼容，
# 需要剔除 Git 收集的 OpenSSL，改用 Python 自带 DLLs 目录下的 libssl/libcrypto
def _is_git_openssl(binary) -> bool:
    """剔除 Analysis 从 Git mingw64 收集的 OpenSSL（版本与 Python 不匹配）。"""
    src = str(binary[1]).lower().replace('\\', '/')
    return 'mingw64' in src and (
        'libssl-3-x64.dll' in src or 'libcrypto-3-x64.dll' in src
    )


def _add_python_openssl(a) -> None:
    """把 Python 自带 DLLs 的 libssl/libcrypto 补进 binaries，避免 _ssl 加载失败。"""
    import pathlib
    ssl_pyd = next(b for b in a.binaries if str(b[0]).lower() == '_ssl.pyd')
    dlls_dir = pathlib.Path(ssl_pyd[1]).parent
    for dll in ('libssl-3-x64.dll', 'libcrypto-3-x64.dll'):
        src = dlls_dir / dll
        if src.exists() and not any(
            str(b[0]).lower() == dll for b in a.binaries
        ):
            a.binaries.append((dll, str(src), 'BINARY'))


a.binaries = [b for b in a.binaries if not (_is_unneeded_binary(b) or _is_unneeded_binary2(b) or _is_git_openssl(b))]
_add_python_openssl(a)
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
