from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from one_dragon.envs.project_config import ProjectConfig
from one_dragon_qt.services.app_setting.app_setting_manager import AppSettingManager
from one_dragon_qt.widgets.back_navigation_button import BackNavigationButton
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from one_dragon_qt.windows.app_window_base import AppWindowBase

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class MainAppWindowBase(AppWindowBase):
    """主应用窗口基类。

    在 AppWindowBase 基础上增加：
    - 接收 OneDragonContext
    - 持有 AppSettingManager，ctx.init() 完成后执行设置发现
    - 导航栏返回按钮
    """

    def __init__(
        self,
        ctx: OneDragonContext,
        win_title: str,
        project_config: ProjectConfig,
        app_icon: str | None = None,
        parent=None,
    ):
        self.app_setting_manager = AppSettingManager(ctx)
        self._connected_pivot_navi: PivotNavigatorInterface | None = None

        AppWindowBase.__init__(
            self,
            win_title=win_title,
            project_config=project_config,
            app_icon=app_icon,
            parent=parent,
        )

    def create_sub_interface(self) -> None:
        # 导航栏返回按钮（最上方，在子界面之前添加）
        self._back_nav_btn = BackNavigationButton(on_click=self._on_back_nav_clicked, parent=self)
        self.add_nav_widget(self._back_nav_btn)
        # 子类应 super().create_sub_interface() 后添加各自的界面

    def init_interface_on_shown(self, index: int) -> None:
        super().init_interface_on_shown(index)
        base_interface = self.stackedWidget.currentWidget()
        self._update_back_btn_for_interface(base_interface)

    def _on_back_nav_clicked(self) -> None:
        """导航栏返回按钮的点击回调。"""
        current = self.stackedWidget.currentWidget()
        if isinstance(current, PivotNavigatorInterface):
            current.pop_setting_interface()

    def _on_secondary_state_changed(self, has_secondary: bool) -> None:
        """二级页面状态变化时更新返回按钮。"""
        self._back_nav_btn.set_active(has_secondary)

    def _update_back_btn_for_interface(self, interface: BaseInterface) -> None:
        """切换界面时，重新连接信号并更新返回按钮状态。"""
        if self._connected_pivot_navi is not None:
            with contextlib.suppress(RuntimeError):
                self._connected_pivot_navi.secondary_state_changed.disconnect(self._on_secondary_state_changed)
            self._connected_pivot_navi = None

        if isinstance(interface, PivotNavigatorInterface):
            interface.secondary_state_changed.connect(self._on_secondary_state_changed)
            self._connected_pivot_navi = interface
            from one_dragon_qt.widgets.page_stack_wrapper import PageStackWrapper
            current_widget = interface.stacked_widget.currentWidget()
            has_secondary = isinstance(current_widget, PageStackWrapper) and current_widget.is_secondary_shown
            self._back_nav_btn.set_active(has_secondary)
        else:
            self._back_nav_btn.set_active(False)

    def on_ctx_ready(self) -> None:
        """在 ctx.init() 完成后调用，执行设置提供者扫描"""
        self.app_setting_manager.discover()
