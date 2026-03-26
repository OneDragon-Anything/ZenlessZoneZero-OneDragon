"""应用设置提供者扫描器

通过文件名约定 (*_app_setting.py) 自动发现并加载 AppSettingProvider。
扫描逻辑与 ApplicationFactoryManager 类似，复用相同的插件目录。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.utils.file_utils import find_src_dir
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.app_setting.app_setting_provider import AppSettingProvider

_MODULE_SUFFIX = "_app_setting"


def scan_app_settings(
    plugin_dirs: list[tuple[Path, PluginSource]],
) -> list[AppSettingProvider]:
    """扫描所有插件目录，发现 *_app_setting.py 并加载 AppSettingProvider。

    Args:
        plugin_dirs: 与 ApplicationFactoryManager 相同的插件目录列表

    Returns:
        已发现的 AppSettingProvider 实例列表
    """
    providers: list[AppSettingProvider] = []
    seen_app_ids: set[str] = set()

    for plugin_dir, source in plugin_dirs:
        if not plugin_dir.is_dir():
            continue
        for setting_file in plugin_dir.rglob("*.py"):
            if not setting_file.stem.endswith(_MODULE_SUFFIX):
                continue
            try:
                provider = _load_provider_from_file(setting_file, source, plugin_dir)
            except Exception:
                log.warning(f"加载应用设置文件失败: {setting_file}", exc_info=True)
                continue
            if provider is None:
                continue
            if provider.app_id in seen_app_ids:
                log.warning(f"重复的应用设置 app_id '{provider.app_id}'，跳过: {setting_file}")
                continue
            seen_app_ids.add(provider.app_id)
            providers.append(provider)

    log.info(f"发现 {len(providers)} 个应用设置提供者")
    return providers


def _load_provider_from_file(
    setting_file: Path,
    source: PluginSource,
    base_dir: Path,
) -> AppSettingProvider | None:
    """从文件加载 AppSettingProvider。"""
    module_root = find_src_dir(setting_file) if source == PluginSource.BUILTIN else base_dir
    if module_root is None:
        log.warning(f"无法确定模块根目录: {setting_file}")
        return None

    try:
        relative_path = setting_file.relative_to(module_root)
    except ValueError:
        log.warning(f"无法计算相对路径: {setting_file}")
        return None

    rel_parts = relative_path.parts
    module_name = ".".join([*rel_parts[:-1], setting_file.stem])

    # 第三方插件：确保 base_dir 在 sys.path 中
    if source == PluginSource.THIRD_PARTY:
        base_dir_str = str(base_dir)
        if base_dir_str not in sys.path:
            sys.path.insert(0, base_dir_str)

    module = _import_module(setting_file, module_name, module_root)
    return _find_provider_in_module(module, module_name)


def _import_module(
    file_path: Path,
    module_name: str,
    module_root: Path,
) -> ModuleType:
    """导入模块（与 ApplicationFactoryManager 相同的中间包处理逻辑）。"""
    if module_name in sys.modules:
        return sys.modules[module_name]

    # 确保中间包已加载
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
            ns_pkg = ModuleType(pkg_name)
            ns_pkg.__path__ = [str(pkg_dir)]
            ns_pkg.__package__ = pkg_name
            sys.modules[pkg_name] = ns_pkg

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


def _find_provider_in_module(
    module: ModuleType, module_name: str
) -> AppSettingProvider | None:
    """在模块中查找唯一的 AppSettingProvider 子类并实例化。"""
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, AppSettingProvider)
            and attr is not AppSettingProvider
            and getattr(attr, "__module__", None) == module_name
        ):
            return attr()
    return None
