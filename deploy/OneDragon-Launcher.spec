# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

from PyInstaller.utils.hooks import collect_submodules

if TYPE_CHECKING:
    from PyInstaller.building.build_main import Analysis
    from PyInstaller.building.api import COLLECT, EXE, PYZ

# 保留的模块树
KEEP_TREES = [
    "one_dragon.envs.git_service",
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

# 把 src 下除了 one_dragon 的其它顶级包全部排除
exclude_roots = [p for p in src_packages if p != "one_dragon"]

# one_dragon 下，排除除 KEEP_TREES 以外的所有子模块
all_one_dragon_modules = set(collect_submodules("one_dragon"))

# 收集需要保留的模块：基础模块 + KEEP_TREES 及其子模块
keep_one_dragon_modules = {"one_dragon", "one_dragon.envs"}
for tree in KEEP_TREES:
    keep_one_dragon_modules.add(tree)
    keep_one_dragon_modules.update(collect_submodules(tree))

exclude_one_dragon = [m for m in all_one_dragon_modules if m not in keep_one_dragon_modules]

excludes = sorted(set(exclude_roots + exclude_one_dragon))


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
