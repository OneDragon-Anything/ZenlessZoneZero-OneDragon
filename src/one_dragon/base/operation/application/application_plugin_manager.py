"""应用插件管理器

提供插件式的应用注册机制，支持动态发现和刷新应用工厂。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application.plugin_info import (
    PluginInfo,
    PluginScanResult,
    PluginSource,
)
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
        self._const_module_suffix: str = "_const"
        self._loaded_modules: set[str] = set()
        self._plugin_infos: dict[str, PluginInfo] = {}  # {app_id: PluginInfo}
        self._last_scan_result: PluginScanResult | None = None

    @property
    def plugin_infos(self) -> list[PluginInfo]:
        """获取所有已加载的插件信息"""
        return list(self._plugin_infos.values())

    @property
    def third_party_plugins(self) -> list[PluginInfo]:
        """获取第三方插件"""
        return [p for p in self._plugin_infos.values() if p.is_third_party]

    def get_plugin_info(self, app_id: str) -> PluginInfo | None:
        """根据 app_id 获取插件信息"""
        return self._plugin_infos.get(app_id)

    @property
    def last_scan_result(self) -> PluginScanResult | None:
        """获取上次扫描结果"""
        return self._last_scan_result

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
        scan_result = PluginScanResult()

        # 清空旧的插件信息
        self._plugin_infos.clear()

        for plugin_dir in self._plugin_dirs:
            # 根据目录名判断来源（plugins 目录为第三方）
            source = PluginSource.THIRD_PARTY if plugin_dir.name == 'plugins' else PluginSource.BUILTIN
            nd, d, infos, failures = self._scan_directory(plugin_dir, reload_modules, source)
            non_default_factories.extend(nd)
            default_factories.extend(d)
            for info in infos:
                self._plugin_infos[info.app_id] = info
            scan_result.plugins.extend(infos)
            scan_result.failed_plugins.extend(failures)

        self._last_scan_result = scan_result
        log.info(f"发现 {len(non_default_factories)} 个非默认组应用, {len(default_factories)} 个默认组应用")
        return non_default_factories, default_factories

    def _scan_directory(
        self,
        directory: Path,
        reload_modules: bool = False,
        source: PluginSource = PluginSource.BUILTIN
    ) -> tuple[list[ApplicationFactory], list[ApplicationFactory], list[PluginInfo], list[tuple[Path, str]]]:
        """扫描目录中的工厂模块

        Args:
            directory: 要扫描的目录
            reload_modules: 是否重新加载模块
            source: 插件来源

        Returns:
            tuple: (非默认组工厂列表, 默认组工厂列表, 插件信息列表, 失败记录列表)
        """
        non_default_factories: list[ApplicationFactory] = []
        default_factories: list[ApplicationFactory] = []
        plugin_infos: list[PluginInfo] = []
        failures: list[tuple[Path, str]] = []

        # 递归查找所有 *_factory.py 文件
        for factory_file in directory.rglob(f"*{self._factory_module_suffix}.py"):
            result = self._load_factory_from_file(factory_file, reload_modules, source)
            if result is None:
                continue

            for factory, is_default, plugin_info in result:
                if is_default:
                    default_factories.append(factory)
                else:
                    non_default_factories.append(factory)
                if plugin_info:
                    plugin_infos.append(plugin_info)

        return non_default_factories, default_factories, plugin_infos, failures

    def _load_factory_from_file(
        self,
        factory_file: Path,
        reload_modules: bool = False,
        source: PluginSource = PluginSource.BUILTIN
    ) -> list[tuple[ApplicationFactory, bool, PluginInfo | None]] | None:
        """从文件加载工厂类

        Args:
            factory_file: 工厂文件路径
            reload_modules: 是否重新加载模块
            source: 插件来源

        Returns:
            list[tuple[ApplicationFactory, bool, PluginInfo | None]]:
                [(工厂实例, 是否默认组, 插件信息), ...]
        """
        results: list[tuple[ApplicationFactory, bool, PluginInfo | None]] = []

        try:
            # 计算模块名
            module_name = self._get_module_name(factory_file)
            if module_name is None:
                return None

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

                        # 读取插件元数据
                        plugin_info = self._read_plugin_metadata(factory, factory_file, module_name, source)

                        results.append((factory, is_default, plugin_info))
                        log.debug(f"加载工厂: {attr_name} (default_group={is_default})")
                    except Exception as e:
                        log.warning(f"实例化工厂 {attr_name} 失败: {e}")

        except Exception as e:
            log.warning(f"加载工厂文件 {factory_file} 失败: {e}")

        return results

    def _get_module_name(self, file_path: Path) -> str | None:
        """根据文件路径获取模块名

        始终返回从 src 目录开始的完整模块路径。
        例如: src/zzz_od/plugins/my_plugin/my_factory.py
        返回: zzz_od.plugins.my_plugin.my_factory

        Args:
            file_path: 文件路径

        Returns:
            str | None: 模块名，如果无法确定则返回 None
        """
        parts = file_path.parts
        try:
            src_index = parts.index('src')
            # 从 src 之后开始构建模块名
            module_parts = list(parts[src_index + 1:])
            # 移除 .py 后缀
            module_parts[-1] = module_parts[-1][:-3]
            return '.'.join(module_parts)
        except ValueError:
            log.warning(f"无法确定模块名，文件不在 src 目录下: {file_path}")
            return None

    def _read_plugin_metadata(
        self,
        factory: ApplicationFactory,
        factory_file: Path,
        factory_module_name: str,
        source: PluginSource
    ) -> PluginInfo:
        """读取插件元数据

        从 factory 对象和对应的 const 模块中读取插件元数据。

        Args:
            factory: 工厂实例
            factory_file: 工厂文件路径
            factory_module_name: 工厂模块名
            source: 插件来源（由调用方根据扫描目录确定）

        Returns:
            PluginInfo: 插件信息
        """
        # 从 factory 获取基本信息
        plugin_info = PluginInfo(
            app_id=factory.app_id,
            app_name=factory.app_name,
            default_group=factory.default_group,
            source=source,
            plugin_dir=factory_file.parent,
            factory_module=factory_module_name,
        )

        # 尝试加载对应的 const 模块
        const_module_name = factory_module_name.replace(
            self._factory_module_suffix,
            self._const_module_suffix
        )

        try:
            if const_module_name in sys.modules:
                const_module = sys.modules[const_module_name]
            else:
                const_module = importlib.import_module(const_module_name)

            plugin_info.const_module = const_module_name

            # 读取可选的插件元数据
            plugin_info.author = getattr(const_module, 'PLUGIN_AUTHOR', '')
            plugin_info.homepage = getattr(const_module, 'PLUGIN_HOMEPAGE', '')
            plugin_info.version = getattr(const_module, 'PLUGIN_VERSION', '')
            plugin_info.description = getattr(const_module, 'PLUGIN_DESCRIPTION', '')

        except ImportError:
            # const 模块不存在，使用默认值
            log.debug(f"未找到 const 模块: {const_module_name}")
        except Exception as e:
            log.warning(f"读取 const 模块 {const_module_name} 失败: {e}")

        return plugin_info

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
