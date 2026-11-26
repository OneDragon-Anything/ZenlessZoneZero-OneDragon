from __future__ import annotations

import contextlib

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QListWidgetItem, QWidget
from qfluentwidgets import (
    FluentIcon,
    FluentIconBase,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    getFont,
)

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_run_context import (
    RunFinishReason,
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.view.app_run_interface import SplitAppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.multi_select_list import MultiSelectListWidget
from one_dragon_qt.widgets.selectable_app_list import SelectableAppList
from one_dragon_qt.windows.main_app_window_base import MainAppWindowBase


class StandaloneRunInterface(SplitAppRunInterface):
    """独立应用运行界面基类

    左侧为用户手动添加的应用卡片列表，
    右侧为标准的运行/停止/日志控件。
    选中某个应用后，点击"开始"即运行该应用。
    """

    def __init__(self, ctx: OneDragonContext,
                 object_name: str = 'standalone_run_interface',
                 nav_text_cn: str = '运行',
                 nav_icon: FluentIconBase | QIcon | str = FluentIcon.PLAY,
                 parent: QWidget | None = None):
        self.ctx: OneDragonContext = ctx
        self._loop_running: bool = False
        self._runner_finished_connected: bool = False

        SplitAppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id='',
            object_name=object_name,
            nav_text_cn=nav_text_cn,
            nav_icon=nav_icon,
            parent=parent,
            left_stretch=1,
            right_stretch=1,
        )

        self._loop_restart_timer = QTimer(self)
        self._loop_restart_timer.setSingleShot(True)
        self._loop_restart_timer.timeout.connect(self._restart_loop_app)

    def get_left_widget(self) -> QWidget:
        left = Column(spacing=4)

        self.app_list_widget = SelectableAppList()
        self.app_list_widget.app_selected.connect(self._on_app_selected)
        self.app_list_widget.app_removed.connect(self._on_app_removed)
        self.app_list_widget.app_setting_clicked.connect(self._on_app_setting_clicked)
        self.app_list_widget.app_order_changed.connect(self._on_app_order_changed)
        left.add_widget(self.app_list_widget, alignment=Qt.AlignmentFlag(0))

        self.add_app_btn = PrimaryPushButton(
            text=gt('添加应用'), icon=FluentIcon.ADD
        )
        self.add_app_btn.clicked.connect(self._on_add_app_clicked)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 16, 0)
        btn_layout.addWidget(self.add_app_btn)
        left.add_widget(btn_container, alignment=Qt.AlignmentFlag(0))

        left.add_stretch(1)
        return left

    def get_content_widget(self) -> QWidget:
        content_widget = SplitAppRunInterface.get_content_widget(self)
        self.loop_btn = PushButton(
            text=f"{gt('循环运行')} F8",
            icon=FluentIcon.SYNC,
        )
        self.loop_btn.clicked.connect(self._on_loop_run_clicked)
        self.btn_row_layout.insertWidget(1, self.loop_btn)
        return content_widget

    def on_interface_shown(self) -> None:
        SplitAppRunInterface.on_interface_shown(self)
        if not self._runner_finished_connected:
            self.app_runner.finished.connect(self._on_app_runner_finished)
            self._runner_finished_connected = True
        self._refresh_app_list()
        self._update_loop_btn_state()

        # AppSettingManager 可能尚未就绪，监听信号以在就绪后刷新
        window = self.window()
        if isinstance(window, MainAppWindowBase):
            window.app_setting_manager.ready.connect(self._update_setting_btn_visibility)

    def on_interface_hidden(self) -> None:
        self._stop_loop_mode()
        SplitAppRunInterface.on_interface_hidden(self)
        window = self.window()
        if isinstance(window, MainAppWindowBase):
            with contextlib.suppress(RuntimeError):
                window.app_setting_manager.ready.disconnect(self._update_setting_btn_visibility)

    def on_context_state_changed(self) -> None:
        SplitAppRunInterface.on_context_state_changed(self)
        self._update_loop_btn_state()

    def _handle_key_press(self, key: str) -> None:
        if key == 'f8' and self.ctx.run_context.is_context_stop and not self._loop_running:
            self._on_loop_run_clicked()
            return
        if key == self.ctx.key_stop_running:
            self._stop_loop_mode()
            return
        SplitAppRunInterface._handle_key_press(self, key)

    def _on_start_clicked(self) -> None:
        if self.ctx.run_context.is_context_stop:
            self._loop_running = False
            self._loop_restart_timer.stop()
            self._update_loop_btn_state()
        SplitAppRunInterface._on_start_clicked(self)

    def _on_stop_clicked(self) -> None:
        self._stop_loop_mode()
        SplitAppRunInterface._on_stop_clicked(self)

    def _on_loop_run_clicked(self) -> None:
        """以循环运行模式启动当前选中的应用。"""
        if not self.app_id:
            log.error('请先选择一个应用')
            return
        if self.app_runner.isRunning() or not self.ctx.run_context.is_context_stop:
            log.error('已有应用在运行中')
            return
        self._loop_running = True
        self._loop_restart_timer.stop()
        self._update_loop_btn_state()
        self.run_app()

    def _stop_loop_mode(self) -> None:
        """退出循环运行模式并取消待执行的自动重启。"""
        self._loop_running = False
        self._loop_restart_timer.stop()
        self._update_loop_btn_state()

    def _update_loop_btn_state(self) -> None:
        if not hasattr(self, 'loop_btn'):
            return
        if self._loop_running:
            self.loop_btn.setText(f"{gt('循环运行中')} F8")
            self.loop_btn.setEnabled(False)
        else:
            self.loop_btn.setText(f"{gt('循环运行')} F8")
            self.loop_btn.setEnabled(self.ctx.run_context.is_context_stop)

    def _on_app_runner_finished(self) -> None:
        if not self._loop_running:
            return
        result = self.app_runner.run_result
        if result is None or result.finish_reason in (
            RunFinishReason.STOPPED,
            RunFinishReason.NOT_STARTED,
        ):
            self._stop_loop_mode()
            return
        log.info(
            '循环运行：本次执行结束（%s），2.5 秒后自动重新开始',
            result.finish_reason.name,
        )
        self._update_loop_btn_state()
        self._loop_restart_timer.start(2500)

    def _restart_loop_app(self) -> None:
        if not self._loop_running:
            return
        if not self.app_id:
            self._stop_loop_mode()
            return
        if not self.ctx.run_context.is_context_stop:
            self.ctx.run_context.stop_running()
        self.run_app()

    # ── 应用列表管理 ──

    def _get_all_apps(self) -> dict[str, str]:
        """获取允许通过通用应用列表选择的应用 {app_id: app_name}"""
        result: dict[str, str] = {}
        for app_id in self.ctx.run_context.standalone_apps:
            name = self.ctx.run_context.get_application_name(app_id)
            result[app_id] = name or app_id
        return result

    def _refresh_app_list(self) -> None:
        """刷新应用列表"""
        all_apps = self._get_all_apps()
        config = self.ctx.standalone_app_config

        valid_ids = [aid for aid in config.app_list if aid in all_apps]

        app_list = [(aid, all_apps[aid]) for aid in valid_ids]
        self.app_list_widget.set_app_list(app_list)
        self._update_setting_btn_visibility()

        active_id = config.active_app_id
        if active_id and active_id in valid_ids:
            target = active_id
        elif valid_ids:
            target = valid_ids[0]
        else:
            target = None

        if target:
            self.app_list_widget.select_app(target)
        self.app_id = target or ''
        self.ctx.standalone_app_config.active_app_id = self.app_id

    # ── 事件处理 ──

    def _on_app_selected(self, app_id: str) -> None:
        self.app_id = app_id
        self.ctx.standalone_app_config.active_app_id = app_id

    def _save_visible_app_list(self, visible_app_ids: list[str]) -> None:
        """更新可见应用顺序，同时保留配置中被过滤的原始 ID。"""
        config = self.ctx.standalone_app_config
        selectable_app_ids = set(self._get_all_apps())
        visible_iter = iter(visible_app_ids)
        merged_app_ids: list[str] = []
        for saved_app_id in config.app_list:
            if saved_app_id not in selectable_app_ids:
                merged_app_ids.append(saved_app_id)
                continue
            visible_app_id = next(visible_iter, None)
            if visible_app_id is not None:
                merged_app_ids.append(visible_app_id)
        merged_app_ids.extend(visible_iter)
        config.app_list = merged_app_ids

    def _on_app_removed(self, app_id: str) -> None:
        self._save_visible_app_list(self.app_list_widget.app_ids)

    def _on_app_order_changed(self, app_ids: list[str]) -> None:
        self._save_visible_app_list(app_ids)

    def _on_add_app_clicked(self) -> None:
        all_apps = self._get_all_apps()
        existing_ids = set(self.app_list_widget.app_ids)
        available = {aid: name for aid, name in all_apps.items() if aid not in existing_ids}

        if not available:
            return

        dialog = AddAppDialog(available, self.window())
        if dialog.exec():
            selected_ids = dialog.get_selected_ids()
            for app_id in selected_ids:
                self.app_list_widget.add_app(app_id, all_apps[app_id])
            self._update_setting_btn_visibility()
            self._save_visible_app_list(self.app_list_widget.app_ids)

    def _on_app_setting_clicked(self, app_id: str) -> None:
        window = self.window()
        if not isinstance(window, MainAppWindowBase):
            return
        target = self._find_setting_btn(app_id) or self.add_app_btn
        window.app_setting_manager.show_app_setting(
            app_id=app_id,
            parent=self,
            group_id=application_const.DEFAULT_GROUP_ID,
            target=target,
        )

    def _find_setting_btn(self, app_id: str) -> QWidget | None:
        """找到对应 app_id 的卡片上的设置按钮"""
        for card in self.app_list_widget._cards:
            if card.app_id == app_id:
                return card.setting_btn
        return None

    def _update_setting_btn_visibility(self) -> None:
        """根据 app_setting_manager 的注册信息，显示或隐藏卡片的设置按钮"""
        window = self.window()
        if not isinstance(window, MainAppWindowBase):
            return
        settable = window.app_setting_manager.settable_app_ids
        for card in self.app_list_widget._cards:
            card.setting_btn.setVisible(card.app_id in settable)


class AddAppDialog(MessageBoxBase):
    """添加应用对话框"""

    def __init__(self, available_apps: dict[str, str], parent: QWidget):
        super().__init__(parent=parent)

        self.titleLabel = SubtitleLabel(gt('添加应用'))
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(10)

        self._app_ids = list(available_apps.keys())

        self._list_widget = MultiSelectListWidget()
        self._list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._list_widget.setViewportMargins(0, 0, 16, 0)
        self._list_widget.setMinimumHeight(400)
        self._list_widget.setMinimumWidth(480)
        item_font = getFont(16)
        for _, app_name in available_apps.items():
            item = QListWidgetItem(gt(app_name))
            item.setSizeHint(QSize(0, 36))
            item.setFont(item_font)
            self._list_widget.addItem(item)

        self.viewLayout.addWidget(self._list_widget)

        self.yesButton.setText(gt('确定'))
        self.cancelButton.setText(gt('取消'))

    def get_selected_ids(self) -> list[str]:
        selected_rows = {idx.row() for idx in self._list_widget.selectedIndexes()}
        return [self._app_ids[i] for i in sorted(selected_rows)]
