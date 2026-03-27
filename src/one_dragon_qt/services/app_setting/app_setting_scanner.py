"""应用设置提供者扫描器

通过文件名约定 (*_app_setting.py) 自动发现并加载 AppSettingProvider。
扫描逻辑与 ApplicationFactoryManager 共享 plugin_module_loader 工具。
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.utils.log_utils import log
from one_dragon.utils.plugin_module_loader import (
    ensure_sys_path,
    import_module_from_file,
    resolve_module_name,
)
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
    result = resolve_module_name(setting_file, source, base_dir)
    if result is None:
        log.warning(f"无法解析模块路径: {setting_file}")
        return None

    module_name, module_root = result

    if source == PluginSource.THIRD_PARTY:
        ensure_sys_path(base_dir)

    module = import_module_from_file(setting_file, module_name, module_root)
    return _find_provider_in_module(module, module_name)


def _find_provider_in_module(
    module: ModuleType, module_name: str
) -> AppSettingProvider | None:
    """在模块中查找唯一的 AppSettingProvider 子类并实例化。"""
    found: list[type[AppSettingProvider]] = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, AppSettingProvider)
            and attr is not AppSettingProvider
            and getattr(attr, "__module__", None) == module_name
        ):
            found.append(attr)

    if len(found) == 0:
        return None
    if len(found) > 1:
        names = [cls.__name__ for cls in found]
        log.warning(f"模块 {module_name} 中发现多个 AppSettingProvider: {names}，仅使用第一个")
    return found[0]()
