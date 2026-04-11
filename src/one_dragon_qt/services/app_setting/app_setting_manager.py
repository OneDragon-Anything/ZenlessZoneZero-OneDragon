"""应用设置管理器

基于 factory_manager 已发现的插件目录扫描 *_app_setting.py，
自动构建 app_id → 设置回调的映射，并负责设置界面的分发显示。

支持两种设置界面显示方式：
- INTERFACE: 推入二级设置界面（替换主内容，返回按钮导航）
- FLYOUT: 每次通过类方法创建 Flyout 并显示
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.utils.log_utils import log
from one_dragon.utils.plugin_module_loader import (
    ensure_sys_path,
    import_module_from_file,
    resolve_module_name,
)
from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    GroupIdMixin,
    SettingType,
)

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext
    from one_dragon_qt.widgets.base_interface import BaseInterface
    from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface


class AppSettingManager(QObject):
    """应用设置管理器

    负责扫描、注册和分发应用设置界面。
    """

    ready = Signal()

    def __init__(self, ctx: OneDragonContext) -> None:
        super().__init__()
        self.ctx: OneDragonContext = ctx
        self._setting_module_suffix: str = "_app_setting"
        self._interface_cache: dict[tuple[int, type], BaseInterface] = {}
        self._app_setting_map: dict[str, Callable[..., None]] = {}

    # ─── 公共 API ─────────────────────────────────────────

    def discover(self) -> None:
        """执行设置提供者扫描并发出 ready 信号。"""
        self._discover_providers()
        self.ready.emit()

    @property
    def settable_app_ids(self) -> set[str]:
        """返回所有已注册设置的 app_id 集合。"""
        return set(self._app_setting_map)

    def show_app_setting(
        self, app_id: str, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        """根据 app_id 查找并调用对应的设置回调。"""
        handler = self._app_setting_map.get(app_id)
        if handler is not None:
            handler(parent=parent, group_id=group_id, target=target)

    # ─── 扫描与注册 ──────────────────────────────────────

    def _discover_providers(self) -> None:
        """扫描 factory_manager.plugin_infos 中的 *_app_setting.py 并注册。"""
        fm = self.ctx.factory_manager
        seen_app_ids: set[str] = set()

        base_dirs: dict[PluginSource, Path] = {}
        for plugin_dir, source in fm.plugin_dirs:
            base_dirs[source] = plugin_dir

        for info in fm.plugin_infos:
            if info.plugin_dir is None or not info.plugin_dir.is_dir():
                continue
            base_dir = base_dirs.get(info.source)
            if base_dir is None:
                continue

            for setting_file in info.plugin_dir.iterdir():
                if (
                    not setting_file.is_file()
                    or setting_file.suffix != '.py'
                    or not setting_file.stem.endswith(self._setting_module_suffix)
                ):
                    continue
                self._try_register_provider(setting_file, info.source, base_dir, seen_app_ids)

        log.info(f"发现 {len(self._app_setting_map)} 个应用设置提供者")

    def _try_register_provider(
        self,
        setting_file: Path,
        source: PluginSource,
        base_dir: Path,
        seen_app_ids: set[str],
    ) -> None:
        """尝试加载并注册单个 provider 文件。"""
        try:
            provider = self._load_provider(setting_file, source, base_dir)
        except Exception:
            log.warning(f"加载应用设置文件失败: {setting_file}", exc_info=True)
            return
        if provider is None:
            return
        if provider.app_id in seen_app_ids:
            log.warning(f"重复的应用设置 app_id '{provider.app_id}'，跳过: {setting_file}")
            return

        seen_app_ids.add(provider.app_id)
        if provider.setting_type == SettingType.INTERFACE:
            self._app_setting_map[provider.app_id] = self._make_interface_handler(provider.get_setting_cls)
        elif provider.setting_type == SettingType.FLYOUT:
            self._app_setting_map[provider.app_id] = self._make_flyout_handler(provider.get_setting_cls)

    @staticmethod
    def _load_provider(
        setting_file: Path, source: PluginSource, base_dir: Path,
    ) -> AppSettingProvider | None:
        """动态导入 setting 文件并查找唯一的 AppSettingProvider 子类。"""
        result = resolve_module_name(setting_file, source, base_dir)
        if result is None:
            log.warning(f"无法解析模块路径: {setting_file}")
            return None

        module_name, module_root = result
        if source == PluginSource.THIRD_PARTY:
            ensure_sys_path(base_dir)

        module = import_module_from_file(setting_file, module_name, module_root)

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

    # ─── UI 分发 ──────────────────────────────────────────

    def _make_interface_handler(self, get_cls: Callable[[], type]) -> Callable[..., None]:
        """创建 INTERFACE 模式的设置回调（推入二级界面）。"""

        def handler(parent: QWidget, group_id: str, target: QWidget) -> None:
            self._push_interface(get_cls(), parent, group_id)

        return handler

    def _make_flyout_handler(self, get_cls: Callable[[], type]) -> Callable[..., None]:
        """创建 FLYOUT 模式的设置回调（弹窗显示）。"""

        def handler(parent: QWidget, group_id: str, target: QWidget) -> None:
            self._show_flyout(get_cls(), parent, group_id, target)

        return handler

    def _push_interface(
        self,
        interface_cls: type,
        parent: QWidget,
        group_id: str,
    ) -> None:
        """在父级 PivotNavigatorInterface 中推入二级设置界面。"""
        pivot_navi = self._find_pivot_navigator(parent)
        if pivot_navi is None:
            return

        cache_key = (id(pivot_navi), interface_cls)
        if cache_key not in self._interface_cache:
            self._interface_cache[cache_key] = interface_cls(self.ctx)

        instance = self._interface_cache[cache_key]
        if isinstance(instance, GroupIdMixin):
            instance.group_id = group_id
        for iface in getattr(instance, 'sub_interfaces', []):
            if isinstance(iface, GroupIdMixin):
                iface.group_id = group_id
        pivot_navi.push_setting_interface(instance.nav_text, instance)

    def _show_flyout(
        self,
        flyout_cls: Any,
        parent: QWidget,
        group_id: str,
        target: QWidget,
    ) -> None:
        """显示 Flyout 风格的设置弹窗（每次新建实例）。"""
        flyout_cls.show_flyout(ctx=self.ctx, group_id=group_id, target=target, parent=parent)

    @staticmethod
    def _find_pivot_navigator(widget: QWidget) -> PivotNavigatorInterface | None:
        """沿父链向上查找最近的 PivotNavigatorInterface。"""
        from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface

        current = widget
        while current is not None:
            if isinstance(current, PivotNavigatorInterface):
                return current
            current = current.parent()
        return None
