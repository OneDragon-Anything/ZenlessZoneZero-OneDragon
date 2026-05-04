"""插件模块加载工具

提供插件式文件发现和动态导入的共享工具函数。
被 ApplicationFactoryManager 和 AppSettingManager 共同使用。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.utils.file_utils import find_src_dir


def resolve_module_name(
    file_path: Path,
    source: PluginSource,
    base_dir: Path,
) -> tuple[str, Path] | None:
    """根据文件路径和插件来源，解析出 dotted module name 和 module_root。

    Args:
        file_path: .py 文件的绝对路径
        source: 插件来源
        base_dir: 扫描根目录（BUILTIN 时忽略，用 find_src_dir；THIRD_PARTY 时用此值）

    Returns:
        (module_name, module_root) 或 None（无法解析时）
    """
    module_root = find_src_dir(file_path) if source == PluginSource.BUILTIN else base_dir
    if module_root is None:
        return None

    try:
        relative_path = file_path.relative_to(module_root)
    except ValueError:
        return None

    rel_parts = relative_path.parts
    module_name = ".".join([*rel_parts[:-1], file_path.stem])
    return module_name, module_root


def ensure_sys_path(directory: Path, added_paths: set[str] | None = None) -> None:
    """确保目录在 sys.path 中（用于第三方插件）。

    Args:
        directory: 要添加的目录
        added_paths: 可选的已添加路径集合，用于去重追踪
    """
    dir_str = str(directory.resolve())
    if dir_str not in sys.path:
        if added_paths is None or dir_str not in added_paths:
            sys.path.insert(0, dir_str)
            if added_paths is not None:
                added_paths.add(dir_str)


def import_module_from_file(
    file_path: Path,
    module_name: str,
    module_root: Path,
    *,
    reload: bool = False,
) -> ModuleType:
    """通过 spec_from_file_location 导入模块，自动处理中间包。

    Args:
        file_path: .py 文件的绝对路径
        module_name: dotted module name
        module_root: 模块根目录（顶层包的父目录）
        reload: 为 True 时强制重新加载已存在的模块

    Returns:
        已加载的模块

    Raises:
        ImportError: 模块导入失败
    """
    if not reload and module_name in sys.modules:
        return sys.modules[module_name]

    # 确保所有中间包已加载
    _ensure_parent_packages(module_name, module_root)

    # 加载目标模块
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法创建模块 spec: {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise

    return module


def _ensure_parent_packages(module_name: str, module_root: Path) -> None:
    """确保 module_name 的所有中间包已注册到 sys.modules。"""
    parts = module_name.split(".")
    for i in range(len(parts) - 1):
        pkg_name = ".".join(parts[: i + 1])
        if pkg_name in sys.modules:
            continue

        pkg_dir = module_root / Path(*parts[: i + 1])
        init_file = pkg_dir / "__init__.py"
        if init_file.exists():
            spec = importlib.util.spec_from_file_location(
                pkg_name, init_file, submodule_search_locations=[str(pkg_dir)]
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[pkg_name] = mod
                try:
                    spec.loader.exec_module(mod)
                except Exception:
                    sys.modules.pop(pkg_name, None)
                    raise
        else:
            # 无 __init__.py 时创建命名空间包
            ns_pkg = ModuleType(pkg_name)
            ns_pkg.__path__ = [str(pkg_dir)]
            ns_pkg.__package__ = pkg_name
            sys.modules[pkg_name] = ns_pkg
