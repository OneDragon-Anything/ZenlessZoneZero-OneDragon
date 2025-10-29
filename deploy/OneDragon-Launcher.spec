# -*- mode: python ; coding: utf-8 -*-

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PyInstaller.utils.hooks import collect_submodules

if TYPE_CHECKING:
    from PyInstaller.building.api import COLLECT, EXE, PYZ
    from PyInstaller.building.build_main import Analysis

# 将源码目录添加到 sys.path,以便 collect_submodules 能找到模块
REPO_ROOT = Path.cwd().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# 保留的模块树
KEEP_TREES = [
    "one_dragon.launcher",
    "one_dragon.version",
]

# 导入 generate_freeze_seed 模块以生成 freeze_seed.py 并获取源码包列表
GEN_PATH = Path.cwd() / "generate_freeze_seed.py"
spec = importlib.util.spec_from_file_location("generate_freeze_seed", str(GEN_PATH))
generate_freeze_seed = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(generate_freeze_seed)

# 这里顺便生成了 freeze_seed.py
src_packages = generate_freeze_seed.main()

# 收集所有源码包的所有子模块
all_src_modules = set()
for package in src_packages:
    all_src_modules.update(collect_submodules(package))

# 收集需要保留的模块：KEEP_TREES 及其所有父模块和子模块
keep_modules = set()

for tree_path in KEEP_TREES:
    # 添加路径本身
    keep_modules.add(tree_path)

    # 添加所有子模块
    keep_modules.update(m for m in all_src_modules if m.startswith(tree_path + "."))

# 排除所有不在保留列表中的模块
excludes = sorted(all_src_modules - keep_modules)


a = Analysis(
    ['..\\src\\zzz_od\\win_exe\\launcher.py', 'freeze_seed.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['_cffi_backend'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook_path_inject.py'],
    excludes=excludes,
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
