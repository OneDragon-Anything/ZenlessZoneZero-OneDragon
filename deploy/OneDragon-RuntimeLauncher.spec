import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyInstaller.building.api import COLLECT, EXE, PYZ
    from PyInstaller.building.build_main import Analysis

DEPLOY_DIR = Path(globals()['SPECPATH']).resolve()
REPO_ROOT = DEPLOY_DIR.parent
SRC_DIR = REPO_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from zzz_od.win_exe.runtime_launcher_profile import ZRuntimeLauncherProfile  # noqa: E402

project_profile = ZRuntimeLauncherProfile()

# 生成第三方依赖种子，供 PyInstaller 收集外部源码所需运行时依赖。
manifest_generator_path = DEPLOY_DIR / 'generate_module_manifest.py'
manifest_spec = importlib.util.spec_from_file_location(
    'generate_module_manifest',
    str(manifest_generator_path),
)
if manifest_spec is None or manifest_spec.loader is None:
    raise FileNotFoundError(f'无法加载模块: {manifest_generator_path}')
manifest_generator = importlib.util.module_from_spec(manifest_spec)
manifest_spec.loader.exec_module(manifest_generator)
manifest_generator.main()

analysis = Analysis(
    [
        str(SRC_DIR / 'zzz_od' / 'win_exe' / 'runtime_launcher_bootstrap.py'),
        str(DEPLOY_DIR / 'module_manifest.py'),
    ],
    pathex=[str(SRC_DIR), str(DEPLOY_DIR)],
    binaries=[],
    datas=[
        (str(DEPLOY_DIR / 'module_manifest.py'), '.'),
        (str(REPO_ROOT / 'config' / 'project.yml'), 'resources/config'),
        (str(REPO_ROOT / 'config' / 'repository.yml'), 'resources/config'),
    ],
    hiddenimports=[
        '_cffi_backend',
        *project_profile.frozen_import_modules,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name='OneDragon-RuntimeLauncher',
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
    icon=[str(REPO_ROOT / 'assets' / 'ui' / 'logo.ico')],
    contents_directory='.runtime',
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OneDragon-RuntimeLauncher',
)
