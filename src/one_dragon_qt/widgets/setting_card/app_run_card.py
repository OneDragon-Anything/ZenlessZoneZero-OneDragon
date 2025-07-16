from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, TransparentToolButton, FluentThemeColor, SwitchButton
from typing import Optional

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon.utils.i18_utils import gt


class AppRunCard(MultiPushSettingCard):

    move_up = Signal(str)
    run = Signal(str)
    switched = Signal(str, bool)

    def __init__(self, app: Application, switch_on: bool = False,
                 parent: Optional[QWidget] = None):
        self.app: Application = app

        self.move_up_btn = TransparentToolButton(FluentIcon.UP, None)
        self.move_up_btn.clicked.connect(self._on_move_up_clicked)

        self.run_btn = TransparentToolButton(FluentIcon.PLAY, None)
        self.run_btn.clicked.connect(self._on_run_clicked)

        self.switch_btn = SwitchButton()
        self.switch_btn.setOnText('')
        self.switch_btn.setOffText('')
        self.switch_btn.setChecked(switch_on)
        self.switch_btn.checkedChanged.connect(self._on_switch_changed)

        MultiPushSettingCard.__init__(
            self,
            btn_list=[self.move_up_btn, self.run_btn, self.switch_btn],
            icon=FluentIcon.GAME,
            title=self.app.op_name,
            parent=parent,
        )

    def update_display(self) -> None:
        """
        更新显示的状态
        :return:
        """
        self.setTitle(self.app.op_name)
        self.setContent(
            '%s %s' % (
                gt('上次运行'),
                self.app.run_record.run_time
            )
        )

        status = self.app.run_record.run_status_under_now
        if status == AppRunRecord.STATUS_SUCCESS:
            icon = FluentIcon.COMPLETED.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
        elif status == AppRunRecord.STATUS_RUNNING:
            icon = FluentIcon.COMPLETED.STOP_WATCH
        elif status == AppRunRecord.STATUS_FAIL:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
        else:
            icon = FluentIcon.INFO
        self.iconLabel.setIcon(icon)

    def _on_move_up_clicked(self) -> None:
        """
        向上移动运行顺序
        :return:
        """
        self.move_up.emit(self.app.app_id)

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

    def set_app(self, app: Application):
        """
        更新对应的app
        :param app:
        :return:
        """
        self.app = app
        self.update_display()

    def setDisabled(self, arg__1: bool) -> None:
        MultiPushSettingCard.setDisabled(self, arg__1)
        self.move_up_btn.setDisabled(arg__1)
        self.run_btn.setDisabled(arg__1)
        self.switch_btn.setDisabled(arg__1)

    def set_switch_on(self, on: bool) -> None:
        self.switch_btn.setChecked(on)
