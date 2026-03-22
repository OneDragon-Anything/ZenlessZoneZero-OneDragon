from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout


class AppSettingManager:
    """应用设置弹窗管理器基类。

    提供 Dialog / Flyout 两种通用弹窗显示逻辑。
    - ``_show_dialog``: 按类缓存实例并通过 ``show_by_group`` 显示。
    - ``_show_flyout``: 每次通过类方法创建 Flyout 并显示。
    """

    def __init__(self) -> None:
        self._dialog_cache: dict[type, Any] = {}

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

    def _show_flyout(
        self,
        flyout_cls: type[AppSettingFlyout],
        ctx,
        parent: QWidget,
        group_id: str,
        target: QWidget,
    ) -> None:
        """显示一个 Flyout 风格的设置弹窗（每次新建）。"""
        flyout_cls.show_flyout(ctx=ctx, group_id=group_id, target=target, parent=parent)
