"""应用插件管理器

提供插件式的应用注册机制，支持动态发现和刷新应用工厂。
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class ApplicationPluginManager:
    """应用插件管理器

    负责扫描、加载和刷新应用工厂，提供插件式的应用注册机制。
    """

    def __init__(self, ctx: OneDragonContext):
        self.ctx: OneDragonContext = ctx
        self._plugin_dirs: list[Path] = []
        self._factory_module_suffix: str = "_factory"
        self._loaded_modules: set[str] = set()

    def add_plugin_dir(self, plugin_dir: str | Path) -> None:
        """添加插件目录

        Args:
            plugin_dir: 插件目录路径
        """
        path = Path(plugin_dir) if isinstance(plugin_dir, str) else plugin_dir
        if path.is_dir() and path not in self._plugin_dirs:
            self._plugin_dirs.append(path)
            log.debug(f"添加插件目录: {path}")

    def discover_factories(
        self,
        reload_modules: bool = False
    ) -> tuple[list[ApplicationFactory], list[ApplicationFactory]]:
        """发现所有应用工厂

        扫描所有插件目录，自动发现并加载应用工厂类。

        Args:
            reload_modules: 是否重新加载已加载的模块

        Returns:
            tuple[list[ApplicationFactory], list[ApplicationFactory]]:
                (非默认组工厂列表, 默认组工厂列表)
        """
        non_default_factories: list[ApplicationFactory] = []
        default_factories: list[ApplicationFactory] = []

        for plugin_dir in self._plugin_dirs:
            nd, d = self._scan_directory(plugin_dir, reload_modules)
            non_default_factories.extend(nd)
            default_factories.extend(d)

        log.info(f"发现 {len(non_default_factories)} 个非默认组应用, {len(default_factories)} 个默认组应用")
        return non_default_factories, default_factories

    def _scan_directory(
        self,
        directory: Path,
        reload_modules: bool = False
    ) -> tuple[list[ApplicationFactory], list[ApplicationFactory]]:
        """扫描目录中的工厂模块

        Args:
            directory: 要扫描的目录
            reload_modules: 是否重新加载模块

        Returns:
            tuple[list[ApplicationFactory], list[ApplicationFactory]]:
                (非默认组工厂列表, 默认组工厂列表)
        """
        non_default_factories: list[ApplicationFactory] = []
        default_factories: list[ApplicationFactory] = []

        # 递归查找所有 *_factory.py 文件
        for factory_file in directory.rglob(f"*{self._factory_module_suffix}.py"):
            factories = self._load_factory_from_file(factory_file, reload_modules)
            for factory, is_default in factories:
                if is_default:
                    default_factories.append(factory)
                else:
                    non_default_factories.append(factory)

        return non_default_factories, default_factories

    def _load_factory_from_file(
        self,
        factory_file: Path,
        reload_modules: bool = False
    ) -> list[tuple[ApplicationFactory, bool]]:
        """从文件加载工厂类

        Args:
            factory_file: 工厂文件路径
            reload_modules: 是否重新加载模块

        Returns:
            list[tuple[ApplicationFactory, bool]]: [(工厂实例, 是否默认组), ...]
        """
        results: list[tuple[ApplicationFactory, bool]] = []

        try:
            # 计算模块名
            module_name = self._get_module_name(factory_file)
            if module_name is None:
                return results

            # 检查是否需要重新加载
            if module_name in sys.modules:
                if reload_modules:
                    # 重新加载模块
                    module = importlib.reload(sys.modules[module_name])
                else:
                    module = sys.modules[module_name]
            else:
                module = importlib.import_module(module_name)

            self._loaded_modules.add(module_name)

            # 查找工厂类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, ApplicationFactory)
                    and attr is not ApplicationFactory
                    and hasattr(attr, '__module__')
                    and attr.__module__ == module_name
                ):
                    try:
                        factory = attr(self.ctx)
                        # 从工厂实例读取 default_group 属性
                        is_default = factory.default_group
                        results.append((factory, is_default))
                        log.debug(f"加载工厂: {attr_name} (default_group={is_default})")
                    except Exception as e:
                        log.warning(f"实例化工厂 {attr_name} 失败: {e}")

        except Exception as e:
            log.warning(f"加载工厂文件 {factory_file} 失败: {e}")

        return results

    def _get_module_name(self, file_path: Path) -> str | None:
        """根据文件路径获取模块名

        Args:
            file_path: 文件路径

        Returns:
            str | None: 模块名，如果无法确定则返回 None
        """
        # 查找 src 目录作为根
        parts = file_path.parts
        try:
            src_index = parts.index('src')
            # 从 src 之后开始构建模块名
            module_parts = list(parts[src_index + 1:])
            # 移除 .py 后缀
            module_parts[-1] = module_parts[-1][:-3]
            return '.'.join(module_parts)
        except ValueError:
            # 没有找到 src 目录，尝试使用相对于插件目录的路径
            for plugin_dir in self._plugin_dirs:
                try:
                    rel_path = file_path.relative_to(plugin_dir)
                    module_parts = list(rel_path.parts)
                    module_parts[-1] = module_parts[-1][:-3]
                    return '.'.join(module_parts)
                except ValueError:
                    continue
            return None

    def refresh_applications(self) -> None:
        """刷新应用注册

        重新扫描所有插件目录，刷新应用注册。
        """
        log.info("开始刷新应用注册...")

        # 清空现有注册
        self.ctx.run_context.clear_applications()
        self.ctx.run_context.default_group_apps.clear()

        # 重新发现并注册
        non_default_factories, default_factories = self.discover_factories(reload_modules=True)

        if non_default_factories:
            self.ctx.run_context.registry_application(non_default_factories, default_group=False)

        if default_factories:
            self.ctx.run_context.registry_application(default_factories, default_group=True)

        # 更新默认应用组
        self.ctx.app_group_manager.set_default_apps(self.ctx.run_context.default_group_apps)

        # 清除应用组配置缓存，使其重新加载
        self.ctx.app_group_manager.clear_config_cache()

        log.info("应用注册刷新完成")
