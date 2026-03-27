from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QWidget

from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    GroupIdMixin,
    SettingType,
)

if TYPE_CHECKING:
    from one_dragon_qt.widgets.base_interface import BaseInterface
    from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface


class AppSettingManager:
    """应用设置管理器。

    从 AppSettingProvider 列表自动构建 app_id → 设置回调的映射。

    支持两种设置界面显示方式：
    - ``SettingType.INTERFACE``: 推入二级设置界面（替换主内容，BreadcrumbBar 导航）。
    - ``SettingType.FLYOUT``: 每次通过类方法创建 Flyout 并显示。
    """

    def __init__(self, ctx, providers: list[AppSettingProvider]) -> None:
        self.ctx = ctx
        self._interface_cache: dict[tuple[int, type], BaseInterface] = {}
        self._app_setting_map: dict[str, Callable[..., None]] = {}

        for p in providers:
            if p.setting_type == SettingType.INTERFACE:
                self._app_setting_map[p.app_id] = self._make_interface_handler(p.get_setting_cls)
            elif p.setting_type == SettingType.FLYOUT:
                self._app_setting_map[p.app_id] = self._make_flyout_handler(p.get_setting_cls)

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

    def _make_interface_handler(
        self, get_cls: Callable[[], type],
    ) -> Callable[..., None]:
        """创建 interface 模式的设置回调。"""

        def handler(parent: QWidget, group_id: str, target: QWidget) -> None:
            self._push_interface(get_cls(), parent, group_id)

        return handler

    def _make_flyout_handler(
        self, get_cls: Callable[[], type],
    ) -> Callable[..., None]:
        """创建 flyout 模式的设置回调。"""

        def handler(parent: QWidget, group_id: str, target: QWidget) -> None:
            self._show_flyout(get_cls(), parent, group_id, target)

        return handler

    def _push_interface(
        self,
        interface_cls: type,
        parent: QWidget,
        group_id: str,
    ) -> None:
        """在父级 PivotNavigatorInterface 中推入二级设置界面。

        Args:
            interface_cls: BaseInterface 子类，构造函数需接受 ctx 作为唯一参数
            parent: 调用方 widget（向上查找 PivotNavigatorInterface）
            group_id: 当前运行组 ID
        """
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
        """显示一个 Flyout 风格的设置弹窗（每次新建）。"""
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
