from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
    from one_dragon_qt.widgets.base_interface import BaseInterface
    from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface


class AppSettingManager:
    """应用设置管理器基类。

    提供三种设置界面显示方式：
    - ``_show_dialog``: 按类缓存实例并通过 ``show_by_group`` 显示。
    - ``_push_interface``: 推入二级设置界面（替换主内容，BreadcrumbBar 导航）。
    - ``_show_flyout``: 每次通过类方法创建 Flyout 并显示。
    """

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self._dialog_cache: dict[type, Any] = {}
        self._interface_cache: dict[str, BaseInterface] = {}

    def _show_dialog(
        self,
        dialog_cls: type,
        ctx,
        parent: QWidget,
        group_id: str,
    ) -> None:
        """按类缓存弹窗实例并通过 show_by_group 显示。

        适用于 AppSettingDialog 和 PivotNavigatorDialog 的子类，
        它们都实现了 ``show_by_group(group_id, parent)``。
        """
        if dialog_cls not in self._dialog_cache:
            self._dialog_cache[dialog_cls] = dialog_cls(ctx=ctx)
        self._dialog_cache[dialog_cls].show_by_group(group_id=group_id, parent=parent)

    def _push_interface(
        self,
        interface_cls: type,
        parent: QWidget,
    ) -> None:
        """在父级 PivotNavigatorInterface 中推入二级设置界面。

        Args:
            interface_cls: BaseInterface 子类，构造函数需接受 ctx 作为唯一参数
            parent: 调用方 widget（向上查找 PivotNavigatorInterface）
        """
        pivot_navi = self._find_pivot_navigator(parent)
        if pivot_navi is None:
            return

        cache_key = interface_cls.__name__
        if cache_key not in self._interface_cache:
            self._interface_cache[cache_key] = interface_cls(self.ctx)

        instance = self._interface_cache[cache_key]
        pivot_navi.push_setting_interface(instance.nav_text, instance)

    def _show_flyout(
        self,
        flyout_cls: type[AppSettingFlyout],
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
