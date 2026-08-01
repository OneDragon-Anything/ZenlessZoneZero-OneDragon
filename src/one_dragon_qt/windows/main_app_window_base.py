from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox
from qfluentwidgets import (
    InfoBar,
    InfoBarIcon,
    InfoBarPosition,
    TeachingTipTailPosition,
)

from one_dragon.base.operation.context_download_request_event import (
    ContextDownloadRequestEvent,
)
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.context_notify_event import ContextNotifyEvent
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.services.app_setting.app_setting_manager import AppSettingManager
from one_dragon_qt.services.download_queue_service import (
    DownloadQueueService,
)
from one_dragon_qt.services.resource_update_coordinator import (
    ResourceUpdateCoordinator,
)
from one_dragon_qt.widgets.back_navigation_button import BackNavigationButton
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.widgets.download_queue_dialog import DownloadQueueDialog
from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from one_dragon_qt.widgets.teaching_tip import TeachingTip
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

    context_notify_signal = Signal(object)
    context_download_request_signal = Signal(object)

    def __init__(
        self,
        ctx: OneDragonContext,
        win_title: str,
        project_config: ProjectConfig,
        app_icon: str | None = None,
        parent=None,
    ):
        self.ctx: OneDragonContext = ctx
        self.app_setting_manager = AppSettingManager(ctx)
        self.ctx.update_service.restore_interrupted_launcher_update()
        self.download_queue = DownloadQueueService(ctx)
        self._connected_pivot_navi: PivotNavigatorInterface | None = None

        AppWindowBase.__init__(
            self,
            win_title=win_title,
            project_config=project_config,
            app_icon=app_icon,
            parent=parent,
        )
        self.download_queue.setParent(self)
        self.download_queue_dialog = DownloadQueueDialog(self.download_queue, self)
        self._download_queue_tip: TeachingTip | None = None
        self.resource_update_coordinator: ResourceUpdateCoordinator = (
            ResourceUpdateCoordinator(
                self.ctx,
                self.download_queue,
                self,
                self.show_download_queue_added_tip,
                self,
            )
        )
        self.titleBar.download_queue_requested.connect(self.download_queue_dialog.show_queue)
        self.download_queue.queue_updated.connect(self._update_download_queue_button)
        self._update_download_queue_button()
        self.titleBar.developer_mode_requested.connect(
            lambda: self.set_developer_mode(True)
        )
        self._apply_developer_mode_visibility()

        self.context_notify_signal.connect(self._show_context_notify)
        self.ctx.listen_event(ContextNotifyEvent.EVENT_ID, self._emit_context_notify)

        self.context_download_request_signal.connect(self._show_download_request_dialog)
        self.ctx.listen_event(ContextDownloadRequestEvent.EVENT_ID, self._emit_download_request)

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

    def _emit_context_notify(self, event: ContextEventItem) -> None:
        """将上下文通知事件通过信号传递到主线程。"""
        if isinstance(event.data, ContextNotifyEvent):
            self.context_notify_signal.emit(event.data)

    def _show_context_notify(self, event: ContextNotifyEvent) -> None:
        """在主窗口展示上下文通知。"""
        InfoBar.new(
            icon=InfoBarIcon[event.level.name],
            title=gt(event.title),
            content=gt(event.content),
            isClosable=True,
            duration=5000,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self,
        )

    def set_developer_mode(self, enabled: bool) -> None:
        """更新开发者模式并立即刷新相关入口。"""
        was_enabled = self.ctx.env_config.developer_mode
        if was_enabled != enabled:
            self.ctx.env_config.developer_mode = enabled
        self._apply_developer_mode_visibility()
        if enabled and not was_enabled:
            InfoBar.success(
                title=gt('开发者模式已开启'),
                content=gt('开发工具和实验功能现在可见'),
                duration=4000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self,
            )

    def _apply_developer_mode_visibility(self) -> None:
        """刷新已经创建的开发者和实验功能控件。"""
        for index in range(self.stackedWidget.count()):
            interface = self.stackedWidget.widget(index)
            updater = getattr(
                interface,
                '_update_developer_visibility',
                None,
            )
            if callable(updater):
                updater()

    def _update_download_queue_button(self) -> None:
        """刷新标题栏下载队列数量。"""
        self.titleBar.set_download_queue_counts(
            self.download_queue.active_count(),
            self.download_queue.failed_count(),
        )

    def show_download_queue(self) -> None:
        """打开下载队列弹窗。"""
        self.download_queue_dialog.show_queue()

    def show_download_queue_added_tip(self, resource_title: str) -> None:
        """在标题栏下载入口旁提示资源已经加入队列。"""
        if self._download_queue_tip is not None:
            with contextlib.suppress(RuntimeError):
                self._download_queue_tip.close()
        self._download_queue_tip = TeachingTip.create(
            target=self.titleBar.downloadQueueButton,
            icon=InfoBarIcon.SUCCESS,
            title=gt('已加入下载队列'),
            content=f'{resource_title} · {gt("点击下载按钮查看进度")}',
            isClosable=False,
            tailPosition=TeachingTipTailPosition.TOP,
            duration=2500,
            parent=self,
        )

    def check_resource_updates(self, force: bool = False) -> None:
        """检查通用资源和项目注册的资源。"""
        coordinator = getattr(self, 'resource_update_coordinator', None)
        if coordinator is not None:
            coordinator.check_updates(force=force)

    def on_welcome_dialog_closed(self) -> None:
        """欢迎弹窗结束后允许展示聚合资源更新弹窗。"""
        self.resource_update_coordinator.on_welcome_dialog_closed()

    def _emit_download_request(self, event: ContextEventItem) -> None:
        """将下载确认请求通过信号传递到主线程。"""
        if isinstance(event.data, ContextDownloadRequestEvent):
            self.context_download_request_signal.emit(event.data)

    def _show_download_request_dialog(self, event: ContextDownloadRequestEvent) -> None:
        """将后端资源下载请求交给框架协调器聚合处理。"""
        self.resource_update_coordinator.add_context_download_request(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """活动下载存在时先请求异步取消，避免强行结束线程。"""
        if not self.download_queue.has_active_tasks():
            super().closeEvent(event)
            return
        answer = QMessageBox.question(
            self,
            gt('下载仍在进行'),
            gt('退出前需要取消正在进行的下载，是否取消全部任务？'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.download_queue.cancel_all()
            self.show_download_queue()
        event.ignore()

    def on_ctx_ready(self) -> None:
        """在 ctx.init() 完成后调用，执行设置提供者扫描"""
        self.app_setting_manager.discover()
