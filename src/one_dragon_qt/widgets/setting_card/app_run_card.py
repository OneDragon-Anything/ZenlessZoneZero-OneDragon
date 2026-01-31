from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    FluentIcon,
    FluentThemeColor,
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

    def __init__(
        self,
        app: ApplicationGroupConfigItem,
        index: int = 0,
        run_record: Optional[AppRunRecord] = None,
        switch_on: bool = False,
        parent: Optional[QWidget] = None,
        enable_opacity_effect: bool = True
    ):
        self.app: ApplicationGroupConfigItem = app
        self.run_record: Optional[AppRunRecord] = run_record

        self.setting_btn = TransparentToolButton(FluentIcon.SETTING, None)
        self.setting_btn.clicked.connect(self._on_setting_clicked)

        self.move_top_btn = TransparentToolButton(FluentIcon.UP, None)
        self.move_top_btn.clicked.connect(self._on_move_top_clicked)

        self.run_btn = TransparentToolButton(FluentIcon.PLAY, None)
        self.run_btn.clicked.connect(self._on_run_clicked)

        self.switch_btn = SwitchButton()
        self.switch_btn.setOnText('')
        self.switch_btn.setOffText('')
        self.switch_btn.setChecked(switch_on)
        self.switch_btn.checkedChanged.connect(self._on_switch_changed)

        # 创建 MultiPushSettingCard 作为 content_widget
        content_widget = MultiPushSettingCard(
            btn_list=[self.setting_btn, self.move_top_btn, self.run_btn, self.switch_btn],
            icon=FluentIcon.GAME,
            title=self.app.app_name,
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

    def update_display(self) -> None:
        """
        更新显示的状态
        :return:
        """
        self.content_widget.setTitle(gt(self.app.app_name))
        if self.run_record is None:
            self.content_widget.setContent('')
        else:
            self.content_widget.setContent(
                '%s %s' % (
                    gt('上次运行'),
                    self.run_record.run_time
                )
            )

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
        self.move_top.emit(self.app.app_id)

    def _on_run_clicked(self) -> None:
        """
        运行应用
        :return:
        """
        self.run.emit(self.app.app_id)

    def _on_switch_changed(self, value: bool) -> None:
        """
        切换开关状态
        :return:
        """
        self.switched.emit(self.app.app_id, value)

    def set_app(
        self,
        app: ApplicationGroupConfigItem,
        run_record: Optional[AppRunRecord] = None,
    ):
        """
        更新对应的app
        :param app:
        :return:
        """
        self.app = app
        self.run_record = run_record
        self.update_display()

    def setDisabled(self, arg__1: bool) -> None:
        self.content_widget.setDisabled(arg__1)
        self.move_top_btn.setDisabled(arg__1)
        self.run_btn.setDisabled(arg__1)
        self.switch_btn.setDisabled(arg__1)

    def set_switch_on(self, on: bool) -> None:
        self.switch_btn.setChecked(on)

    def _on_setting_clicked(self) -> None:
        """
        点击设置按钮
        """
        self.setting_clicked.emit(self.app.app_id)