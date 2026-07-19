from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    Action,
    FluentIcon,
    FluentThemeColor,
    RoundMenu,
    SwitchButton,
    TransparentToolButton,
)

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfigItem,
)
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.draggable_list import DraggableListItem
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)


class AppRunCard(DraggableListItem):

    move_top = Signal(str)  # 置顶功能，用于拖拽不能处理滚动的场景
    run = Signal(str)
    switched = Signal(str, bool)
    setting_clicked = Signal(str)
    notify_clicked = Signal(str)

    def __init__(
        self,
        app: ApplicationGroupConfigItem | None = None,
        index: int = 0,
        run_record: AppRunRecord | None = None,
        switch_on: bool = False,
        parent: QWidget | None = None,
        enable_opacity_effect: bool = True
    ):
        self.app: ApplicationGroupConfigItem | None = app
        self.run_record: AppRunRecord | None = run_record
        self._notify_action_visible: bool = True
        self._context_menu_enabled: bool = True
        self._active_context_menu: RoundMenu | None = None

        self.setting_btn = TransparentToolButton(FluentIcon.SETTING, None)
        self.setting_btn.setToolTip(gt('应用设置'))
        self.setting_btn.clicked.connect(self._on_setting_clicked)

        self.run_btn = TransparentToolButton(FluentIcon.PLAY, None)
        self.run_btn.setToolTip(gt('运行'))
        self.run_btn.clicked.connect(self._on_run_clicked)

        self.switch_btn = SwitchButton()
        self.switch_btn.setOnText('')
        self.switch_btn.setOffText('')
        self.switch_btn.setChecked(switch_on)
        self.switch_btn.checkedChanged.connect(self._on_switch_changed)

        # 创建 MultiPushSettingCard 作为 content_widget
        content_widget = MultiPushSettingCard(
            btn_list=[self.setting_btn, self.run_btn, self.switch_btn],
            icon=FluentIcon.GAME,
            title=gt(app.app_name) if app is not None else '',
            parent=parent,
        )

        # 调用 DraggableListItem 的 __init__
        DraggableListItem.__init__(
            self,
            data=app,
            index=index,
            content_widget=content_widget,
            parent=parent,
            enable_opacity_effect=enable_opacity_effect
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        content_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        content_widget.customContextMenuRequested.connect(self._show_context_menu_from_content)
        self.set_app(app, run_record)
        self.set_switch_on(switch_on)

    def update_display(self) -> None:
        """
        更新显示的状态
        :return:
        """
        if self.app is None:
            self.content_widget.setTitle('')
            self.content_widget.setContent('')
            self.content_widget.iconLabel.setIcon(FluentIcon.GAME)
            return

        self.content_widget.setTitle(gt(self.app.app_name))
        if self.run_record is None:
            self.content_widget.setContent('')
        else:
            self.content_widget.setContent(f"{gt('上次运行')} {self.run_record.run_time}")

            status = self.run_record.run_status_under_now
            if status == AppRunRecord.STATUS_SUCCESS:
                icon = FluentIcon.COMPLETED.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
            elif status == AppRunRecord.STATUS_RUNNING:
                icon = FluentIcon.COMPLETED.STOP_WATCH
            elif status == AppRunRecord.STATUS_FAIL:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            else:
                icon = FluentIcon.INFO
            self.content_widget.iconLabel.setIcon(icon)

    def _on_move_top_clicked(self) -> None:
        """
        置顶运行顺序（用于拖拽不能处理滚动的场景）
        :return:
        """
        if self.app is None:
            return
        self.move_top.emit(self.app.app_id)

    def _show_context_menu_from_content(self, pos: QPoint) -> None:
        """
        从内部卡片内容触发右键菜单。
        """
        self._show_context_menu(self.content_widget.mapTo(self, pos))

    def _show_context_menu(self, pos: QPoint) -> None:
        """
        临时创建低频操作菜单。
        """
        if self.app is None or not self._context_menu_enabled:
            return

        if self._active_context_menu is not None:
            self._active_context_menu.close()

        menu = RoundMenu(parent=self)
        menu.aboutToHide.connect(self._on_context_menu_hidden)

        if self._notify_action_visible:
            notify_action = Action(FluentIcon.MESSAGE, gt('通知设置'), menu)
            notify_action.triggered.connect(lambda _checked=False: self._on_notify_clicked())
            menu.addAction(notify_action)

        move_top_action = Action(FluentIcon.PIN, gt('移到顶部'), menu)
        move_top_action.triggered.connect(lambda _checked=False: self._on_move_top_clicked())
        menu.addAction(move_top_action)

        self._active_context_menu = menu
        menu.popup(self.mapToGlobal(pos))

    def _on_context_menu_hidden(self) -> None:
        """
        右键菜单关闭后释放临时菜单。
        """
        if self._active_context_menu is None:
            return
        self._active_context_menu.deleteLater()
        self._active_context_menu = None

    def _on_run_clicked(self) -> None:
        """
        运行应用
        :return:
        """
        if self.app is None:
            return
        self.run.emit(self.app.app_id)

    def _on_switch_changed(self, value: bool) -> None:
        """
        切换开关状态
        :return:
        """
        if self.app is None:
            return
        self.switched.emit(self.app.app_id, value)

    def set_app(
        self,
        app: ApplicationGroupConfigItem | None,
        run_record: AppRunRecord | None = None,
    ) -> None:
        """
        更新对应的app
        :param app:
        :return:
        """
        self.app = app
        self.data = app
        self.run_record = run_record
        self.update_display()

    def setDisabled(self, arg__1: bool) -> None:
        self._context_menu_enabled = not arg__1
        self.content_widget.setDisabled(arg__1)
        self.setting_btn.setDisabled(arg__1)
        self.run_btn.setDisabled(arg__1)
        self.switch_btn.setDisabled(arg__1)

    def set_switch_on(self, on: bool) -> None:
        self.switch_btn.blockSignals(True)
        self.switch_btn.setChecked(on)
        self.switch_btn.blockSignals(False)

    def set_notify_visible(self, visible: bool) -> None:
        """
        设置通知菜单项是否可见。
        """
        self._notify_action_visible = visible

    def _on_setting_clicked(self) -> None:
        """
        点击设置按钮
        """
        if self.app is None:
            return
        self.setting_clicked.emit(self.app.app_id)

    def _on_notify_clicked(self) -> None:
        """
        点击通知设置按钮
        """
        if self.app is None:
            return
        self.notify_clicked.emit(self.app.app_id)
