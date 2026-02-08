"""应用工厂管理器

提供插件式的应用注册机制，支持动态发现和刷新应用工厂。

支持两种插件来源：
- BUILTIN: 内置插件，位于 src/zzz_od/application 目录
- THIRD_PARTY: 第三方插件，位于项目根目录 plugins 目录
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from one_dragon.base.operation.application.app_const_schema import (
    REQUIRED_CONST_FIELDS,
)
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application.plugin_info import (
    PluginInfo,
    PluginSource,
)
from one_dragon.utils.file_utils import find_src_dir
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class ApplicationFactoryManager:
    """应用工厂管理器

    负责扫描、加载和刷新应用工厂，提供插件式的应用注册机制。
    """

    def __init__(self, ctx: OneDragonContext, plugin_dirs: list[tuple[Path | str, PluginSource]]):
        """初始化应用工厂管理器

        Args:
            ctx: OneDragon 上下文
            plugin_dirs: 插件目录列表，每项为 (path, source) 元组
        """
        self.ctx: OneDragonContext = ctx
        self._plugin_dirs: list[tuple[Path, PluginSource]] = [
            (Path(d) if isinstance(d, str) else d, s) for d, s in plugin_dirs
        ]
        self._factory_module_suffix: str = "_factory"
        self._const_module_suffix: str = "_const"
        self._plugin_infos: dict[str, PluginInfo] = {}  # {app_id: PluginInfo}
        self._scan_failures: list[tuple[Path, str]] = []  # 最近一次扫描的失败记录
        self._added_sys_paths: set[str] = set()  # 跟踪已添加到 sys.path 的路径

    @property
    def plugin_dirs(self) -> list[tuple[Path, PluginSource]]:
        """获取插件目录列表"""
        return self._plugin_dirs

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
    def scan_failures(self) -> list[tuple[Path, str]]:
        """获取最近一次扫描的失败记录"""
        return self._scan_failures

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

        # 清空旧的插件信息
        self._plugin_infos.clear()
        self._scan_failures.clear()

        for plugin_dir, source in self._plugin_dirs:
            if not plugin_dir.is_dir():
                continue
            non_default, default = self._scan_directory(plugin_dir, reload_modules, source)
            non_default_factories.extend(non_default)
            default_factories.extend(default)

        log.info(
            f"发现 {len(non_default_factories)} 个非默认组应用, "
            f"{len(default_factories)} 个默认组应用, "
            f"{len(self._scan_failures)} 个失败"
        )
        return non_default_factories, default_factories

    def _scan_directory(
        self,
        directory: Path,
        reload_modules: bool = False,
        source: PluginSource = PluginSource.BUILTIN
    ) -> tuple[list[ApplicationFactory], list[ApplicationFactory]]:
        """扫描目录中的工厂模块

        Args:
            directory: 要扫描的目录
            reload_modules: 是否重新加载模块
            source: 插件来源

        Returns:
            tuple: (非默认组工厂列表, 默认组工厂列表)
        """
        non_default_factories: list[ApplicationFactory] = []
        default_factories: list[ApplicationFactory] = []

        # 一次性扫描所有 .py 文件，按后缀分组
        factory_files: list[Path] = []
        const_files: list[Path] = []
        for f in directory.rglob("*.py"):
            if f.stem.endswith(self._factory_module_suffix):
                factory_files.append(f)
            elif f.stem.endswith(self._const_module_suffix):
                const_files.append(f)

        # 检测同一目录下多个 factory 或 const 文件
        conflict_dirs: set[Path] = set()
        for files, label in [
            (factory_files, '工厂'),
            (const_files, '常量'),
        ]:
            dir_to_files: dict[Path, list[Path]] = {}
            for f in files:
                dir_to_files.setdefault(f.parent, []).append(f)
            for parent_dir, grouped in dir_to_files.items():
                if len(grouped) > 1:
                    conflict_dirs.add(parent_dir)
                    names = ', '.join(f.name for f in grouped)
                    error_msg = f"同一目录下存在多个{label}文件: {names}"
                    for f in grouped:
                        self._scan_failures.append((f, error_msg))
                    log.warning(f"目录 {parent_dir} 中发现多个{label}文件，已跳过: {names}")

        for factory_file in factory_files:
            if factory_file.parent in conflict_dirs:
                continue
            try:
                result = self._load_factory_from_file(factory_file, reload_modules, source, directory)
                if result is None:
                    self._scan_failures.append((factory_file, "No ApplicationFactory subclass found"))
                    continue

                factory, is_default = result
                if is_default:
                    default_factories.append(factory)
                else:
                    non_default_factories.append(factory)
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                self._scan_failures.append((factory_file, error_msg))
                log.warning(f"加载工厂文件 {factory_file} 失败: {error_msg}")

        return non_default_factories, default_factories

    def _load_factory_from_file(
        self,
        factory_file: Path,
        reload_modules: bool = False,
        source: PluginSource = PluginSource.BUILTIN,
        base_dir: Path | None = None
    ) -> tuple[ApplicationFactory, bool] | None:
        """从文件加载工厂类

        每个工厂模块应只包含一个 ApplicationFactory 子类。
        统一使用 spec_from_file_location 加载所有类型的插件。
        对于 THIRD_PARTY 插件，会将 plugins 目录加入 sys.path 以支持相对导入。

        Args:
            factory_file: 工厂文件路径
            reload_modules: 是否重新加载模块
            source: 插件来源
            base_dir: 扫描根目录（由 _scan_directory 传入）

        Returns:
            tuple[ApplicationFactory, bool] | None:
                (工厂实例, 是否默认组)，未找到工厂类则返回 None

        Raises:
            ImportError: 模块导入失败
            Other exceptions: 工厂加载或实例化时的其他错误
        """
        # 1. 统一解析 module_root（模块名的起算目录）
        module_root = find_src_dir(factory_file) if source == PluginSource.BUILTIN else base_dir
        if module_root is None:
            raise ImportError(f"无法确定模块根目录: {factory_file}")

        # 2. 统一计算 module_name：相对路径 → dotted name
        try:
            relative_path = factory_file.relative_to(module_root)
        except ValueError as e:
            raise ImportError(f"无法计算相对路径: {factory_file} relative to {module_root}") from e

        rel_parts = relative_path.parts
        if len(rel_parts) < 1:
            raise ImportError(f"无效的插件路径: {relative_path}")

        # 第三方插件必须放在子目录中（如 plugins/my_plugin/xxx_factory.py）
        if source == PluginSource.THIRD_PARTY and len(rel_parts) < 2:
            raise ImportError(
                f"第三方插件不能直接放在 plugins 根目录: {factory_file.name}，"
                f"请放在子目录中（如 plugins/my_plugin/{factory_file.name}）"
            )

        module_name = '.'.join(list(rel_parts[:-1]) + [factory_file.stem])

        # 3. THIRD_PARTY 特殊处理：将 plugins 目录加入 sys.path
        if source == PluginSource.THIRD_PARTY:
            module_root_str = str(module_root)
            if module_root_str not in sys.path and module_root_str not in self._added_sys_paths:
                sys.path.insert(0, module_root_str)
                self._added_sys_paths.add(module_root_str)
                log.debug(f"添加到 sys.path: {module_root}")

        # 4. 模块加载/重载
        if module_name in sys.modules:
            if reload_modules:
                unload_prefix = self._get_unload_prefix(module_name, source, rel_parts)
                if unload_prefix:
                    self._unload_plugin_modules(unload_prefix)
                module = self._import_module_from_file(factory_file, module_name, module_root)
            else:
                module = sys.modules[module_name]
        else:
            module = self._import_module_from_file(factory_file, module_name, module_root)

        # 5. 查找并实例化工厂类（每个模块最多一个）
        factory_result = self._find_factory_in_module(
            module, module_name, factory_file, source
        )

        return factory_result

    def _import_module_from_file(
        self,
        factory_file: Path,
        module_name: str,
        module_root: Path
    ) -> ModuleType:
        """使用 spec_from_file_location 导入模块

        统一的模块导入方法，支持相对导入。
        会自动加载所有中间包的 __init__.py，以支持嵌套子目录结构。

        Args:
            factory_file: 工厂文件路径
            module_name: 模块名
            module_root: 模块根目录（顶层包的父目录，如 src/ 或 plugins/）

        Returns:
            module: 导入的模块
        """
        # 确保所有中间包被加载（支持嵌套子目录）
        parts = module_name.split('.')
        for i in range(len(parts) - 1):  # 不包括最后一个（工厂模块本身）
            pkg_module_name = '.'.join(parts[:i + 1])
            if pkg_module_name in sys.modules:
                continue

            pkg_dir = module_root / Path(*parts[:i + 1])
            init_file = pkg_dir / '__init__.py'
            if init_file.exists():
                init_spec = importlib.util.spec_from_file_location(
                    pkg_module_name,
                    init_file,
                    submodule_search_locations=[str(pkg_dir)]
                )
                if init_spec and init_spec.loader:
                    init_module = importlib.util.module_from_spec(init_spec)
                    sys.modules[pkg_module_name] = init_module
                    try:
                        init_spec.loader.exec_module(init_module)
                    except Exception:
                        sys.modules.pop(pkg_module_name, None)
                        raise
            else:
                # 无 __init__.py 时创建命名空间包，确保 dotted import 正常工作
                ns_pkg = ModuleType(pkg_module_name)
                ns_pkg.__path__ = [str(pkg_dir)]
                ns_pkg.__package__ = pkg_module_name
                sys.modules[pkg_module_name] = ns_pkg

        # 加载工厂模块
        spec = importlib.util.spec_from_file_location(
            module_name,
            factory_file,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"无法创建模块 spec: {factory_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise

        return module

    def _get_unload_prefix(
        self,
        module_name: str,
        source: PluginSource,
        rel_parts: tuple[str, ...]
    ) -> str | None:
        """获取热更新时需要卸载的模块前缀

        - THIRD_PARTY: 卸载整个插件包（如 my_plugin 及其所有子模块）
        - BUILTIN: 仅卸载当前应用目录（如 zzz_od.application.xxx 下的模块）

        Args:
            module_name: 完整模块名
            source: 插件来源
            rel_parts: 相对路径各部分（module_root 之后的路径段）

        Returns:
            str | None: 需要卸载的模块前缀
        """
        if source == PluginSource.THIRD_PARTY:
            # 卸载整个插件包：取相对路径第一段（插件包名）
            return rel_parts[0] if rel_parts else None
        else:
            # BUILTIN: 仅卸载当前 factory 所在的父包
            # 例如 zzz_od.application.xxx.xxx_factory -> zzz_od.application.xxx
            parent, _, _ = module_name.rpartition('.')
            return parent or None

    def _unload_plugin_modules(self, pkg_name: str) -> None:
        """卸载插件的所有模块

        Args:
            pkg_name: 插件包名或模块前缀
        """
        modules_to_remove = [
            name for name in sys.modules
            if name == pkg_name or name.startswith(f"{pkg_name}.")
        ]
        for name in modules_to_remove:
            del sys.modules[name]
        log.debug(f"卸载插件模块: {modules_to_remove}")

    def _find_factory_in_module(
        self,
        module: ModuleType,
        module_name: str,
        factory_file: Path,
        source: PluginSource
    ) -> tuple[ApplicationFactory, bool] | None:
        """在模块中查找工厂类

        每个工厂模块应只包含一个 ApplicationFactory 子类。
        实例化失败时异常会向上传播，由调用方记录到 failures。

        Args:
            module: 已加载的模块
            module_name: 模块名
            factory_file: 工厂文件路径
            source: 插件来源

        Returns:
            tuple | None: (工厂实例, 是否默认组)，未找到工厂类则返回 None

        Raises:
            Exception: 工厂实例化或元数据读取失败
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, ApplicationFactory)
                and attr is not ApplicationFactory
                and hasattr(attr, '__module__')
                and attr.__module__ == module_name
            ):
                factory = attr(self.ctx)
                is_default = factory.default_group
                self._register_plugin_metadata(
                    factory, factory_file, module_name, source
                )
                log.debug(f"加载工厂: {attr_name} (default_group={is_default})")
                return factory, is_default

        return None

    def _register_plugin_metadata(
        self,
        factory: ApplicationFactory,
        factory_file: Path,
        factory_module_name: str,
        source: PluginSource
    ) -> PluginInfo:
        """验证并注册插件元数据

        从 factory 对象和对应的 const 模块中读取插件元数据，
        验证必需字段和 APP_ID 唯一性，然后注册到 _plugin_infos。

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
        *prefix_parts, last_part = factory_module_name.rsplit('.', 1)
        if last_part.endswith(self._factory_module_suffix):
            last_part = last_part[:-len(self._factory_module_suffix)] + self._const_module_suffix
        const_module_name = f"{prefix_parts[0]}.{last_part}" if prefix_parts else last_part

        if const_module_name in sys.modules:
            const_module = sys.modules[const_module_name]
        else:
            try:
                const_module = importlib.import_module(const_module_name)
            except (ImportError, ModuleNotFoundError) as e:
                raise ImportError(f"插件 {factory.app_id} 缺少必需的元数据模块 {const_module_name}") from e

        plugin_info.const_module = const_module_name

        # 验证必需字段
        missing = [f for f in REQUIRED_CONST_FIELDS if not hasattr(const_module, f)]
        if missing:
            raise ImportError(
                f"插件 {factory.app_id} 的元数据模块 {const_module_name} "
                f"缺少必需字段: {', '.join(missing)}"
            )

        # 检测重复 APP_ID
        if factory.app_id in self._plugin_infos:
            existing = self._plugin_infos[factory.app_id]
            raise ImportError(
                f"重复的 APP_ID '{factory.app_id}'，"
                f"当前模块 {const_module_name}，"
                f"首次注册于 {existing.const_module}"
            )

        # 读取可选的插件元数据
        plugin_info.author = getattr(const_module, 'PLUGIN_AUTHOR', '')
        plugin_info.homepage = getattr(const_module, 'PLUGIN_HOMEPAGE', '')
        plugin_info.version = getattr(const_module, 'PLUGIN_VERSION', '')
        plugin_info.description = getattr(const_module, 'PLUGIN_DESCRIPTION', '')

        # 注册到插件信息表（同时作为后续重复检测的依据）
        self._plugin_infos[plugin_info.app_id] = plugin_info

        return plugin_info
