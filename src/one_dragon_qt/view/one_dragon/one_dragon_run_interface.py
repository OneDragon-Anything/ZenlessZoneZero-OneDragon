from __future__ import annotations

import contextlib

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    FluentIcon,
    PushButton,
    SettingCardGroup,
)

from one_dragon.base.config.one_dragon_config import AfterDoneOpEnum, InstanceRun
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
    ApplicationGroupConfigItem,
)
from one_dragon.base.operation.application_base import ApplicationEventId
from one_dragon.base.operation.one_dragon_context import (
    ContextInstanceEventEnum,
    OneDragonContext,
)
from one_dragon.utils import cmd_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.view.app_run_interface import SplitAppRunInterface
from one_dragon_qt.view.context_event_signal import ContextEventSignal
from one_dragon_qt.widgets.app_run_list import AppRunList
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.notify_dialog import NotifyDialog
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.windows.main_app_window_base import MainAppWindowBase


class OneDragonRunInterface(SplitAppRunInterface):

    run_all_apps_signal = Signal()

    def __init__(self, ctx: OneDragonContext,
                 nav_text_cn: str = '一条龙运行',
                 object_name: str = 'one_dragon_run_interface',
                 need_multiple_instance: bool = True,
                 need_after_done_opt: bool = True,
                 help_url: str | None = None, parent=None):
        self.config: ApplicationGroupConfig | None = None
        self._context_event_signal = ContextEventSignal()
        self.help_url: str = help_url
        self.need_multiple_instance: bool = need_multiple_instance
        self.need_after_done_opt: bool = need_after_done_opt

        SplitAppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=application_const.ONE_DRAGON_APP_ID,
            object_name=object_name,
            nav_text_cn=nav_text_cn,
            parent=parent,
        )

    def get_left_widget(self) -> QWidget:
        self.app_run_list = AppRunList(self.ctx)
        self.app_run_list.app_list_changed.connect(self._on_app_list_changed)
        self.app_run_list.app_run_clicked.connect(self._on_app_card_run)
        self.app_run_list.app_switch_changed.connect(self.on_app_switch_run)
        self.app_run_list.app_setting_clicked.connect(self.on_app_setting_clicked)
        return self.app_run_list

    def get_widget_at_top(self) -> QWidget:
        top = Column()

        run_group = SettingCardGroup(gt('运行设置'))
        top.add_widget(run_group)

        if self.help_url is not None:
            self.help_opt = HelpCard(url=self.help_url)
            run_group.addSettingCard(self.help_opt)

        self.notify_switch = SwitchSettingCard(icon=FluentIcon.INFO, title='单应用通知')
        self.notify_btn = PushButton(text=gt('设置'), icon=FluentIcon.SETTING)
        self.notify_btn.clicked.connect(self._on_notify_setting_clicked)
        self.notify_switch.hBoxLayout.addWidget(self.notify_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.notify_switch.hBoxLayout.addSpacing(16)
        run_group.addSettingCard(self.notify_switch)

        self.instance_run_opt = ComboBoxSettingCard(icon=FluentIcon.PEOPLE, title='运行实例',
                                                    options_enum=InstanceRun)
        self.instance_run_opt.value_changed.connect(self._on_instance_run_changed)
        run_group.addSettingCard(self.instance_run_opt)

        self.after_done_opt = ComboBoxSettingCard(icon=FluentIcon.CALENDAR, title='结束后',
                                                  options_enum=AfterDoneOpEnum)
        self.after_done_opt.value_changed.connect(self._on_after_done_changed)
        run_group.addSettingCard(self.after_done_opt)

        return top

    def _init_app_list(self) -> None:
        """
        初始化应用列表
        :return:
        """
        self.app_run_list.set_app_list(
            app_list=self.config.app_list,
            instance_idx=self.ctx.current_instance_idx
        )

    def on_interface_shown(self) -> None:
        SplitAppRunInterface.on_interface_shown(self)
        self.config = self.ctx.app_group_manager.get_one_dragon_group_config(
            instance_idx=self.ctx.current_instance_idx,
        )
        self._init_app_list()
        self.notify_switch.init_with_adapter(self.ctx.notify_config.get_prop_adapter('enable_notify'))

        self.ctx.listen_event(ApplicationEventId.APPLICATION_START.value, self._on_app_state_changed)
        self.ctx.listen_event(ApplicationEventId.APPLICATION_STOP.value, self._on_app_state_changed)
        self.ctx.listen_event(ContextInstanceEventEnum.instance_active.value, self._on_instance_event)

        self.instance_run_opt.blockSignals(True)
        self.instance_run_opt.setValue(self.ctx.one_dragon_config.instance_run)
        self.instance_run_opt.setVisible(self.need_multiple_instance)
        self.instance_run_opt.blockSignals(False)

        self.after_done_opt.setValue(self.ctx.one_dragon_config.after_done)
        self.after_done_opt.setVisible(self.need_after_done_opt)

        self._context_event_signal.instance_changed.connect(self._on_instance_changed)
        self.run_all_apps_signal.connect(self.run_app)

        if self.ctx.signal.start_onedragon:
            self.ctx.signal.start_onedragon = False
            self.run_all_apps_signal.emit()

        self._update_setting_btn_visibility()

        # AppSettingManager 可能尚未就绪，监听信号以在就绪后刷新
        window = self.window()
        if isinstance(window, MainAppWindowBase):
            window.app_setting_manager.ready.connect(self._update_setting_btn_visibility)

    def on_interface_hidden(self) -> None:
        SplitAppRunInterface.on_interface_hidden(self)
        with contextlib.suppress(RuntimeError):
            self._context_event_signal.instance_changed.disconnect(self._on_instance_changed)
        window = self.window()
        if isinstance(window, MainAppWindowBase):
            with contextlib.suppress(RuntimeError):
                window.app_setting_manager.ready.disconnect(self._update_setting_btn_visibility)

    def _on_after_done_changed(self, idx: int, value: str) -> None:
        """
        结束后的操作
        :param value:
        :return:
        """
        self.ctx.one_dragon_config.after_done = value
        if value != AfterDoneOpEnum.SHUTDOWN.value.value:
            log.info('已取消关机计划')
            cmd_utils.cancel_shutdown_sys()

    def run_app_by_item(self, app: ApplicationGroupConfigItem) -> None:
        if self.app_runner.isRunning():
            log.error('已有应用在运行中')
            return
        self.app_runner.app_id = app.app_id
        self.app_runner.start()

    def on_context_state_changed(self) -> None:
        SplitAppRunInterface.on_context_state_changed(self)
        self.app_run_list.update_cards_display()

        if self.ctx.run_context.is_context_stop and self.need_after_done_opt:
            if self.ctx.one_dragon_config.after_done == AfterDoneOpEnum.SHUTDOWN.value.value:
                cmd_utils.shutdown_sys(60)
            elif self.ctx.one_dragon_config.after_done == AfterDoneOpEnum.CLOSE_GAME.value.value:
                self.ctx.controller.close_game()

    def _on_app_state_changed(self, event) -> None:
        self.app_run_list.update_cards_display()

    def _on_app_list_changed(self, new_app_list: list[ApplicationGroupConfigItem]) -> None:
        """
        应用列表改变后的回调（拖拽排序或置顶）

        Args:
            new_app_list: 新顺序的应用列表
        """
        # 更新配置中的 app_list 顺序
        self.config.app_list = new_app_list
        self.config.save_app_list()

    def _on_app_card_run(self, app_id: str) -> None:
        """
        运行某个特殊的应用
        :param app_id:
        :return:
        """
        for app in self.config.app_list:
            if app.app_id == app_id:
                self.run_app_by_item(app)

    def on_app_switch_run(self, app_id: str, value: bool) -> None:
        """
        应用运行状态切换
        :param app_id:
        :param value:
        :return:
        """
        self.config.set_app_enable(app_id, value)

    def _on_instance_event(self, event) -> None:
        """
        实例变更 这是context的事件 不能改UI
        :return:
        """
        self._context_event_signal.instance_changed.emit()

    def _on_instance_changed(self) -> None:
        """
        实例变更 这是signal 可以改ui
        :return:
        """
        self._init_app_list()

    def _on_instance_run_changed(self, idx: int, value: str) -> None:
        self.ctx.one_dragon_config.instance_run = value

    def _init_notify_switch(self) -> None:
        pass

    def _on_notify_setting_clicked(self) -> None:
        self.show_notify_dialog()

    def show_notify_dialog(self) -> None:
        """
        显示通知设置对话框。配置更新由对话框内部处理。
        """
        dialog = NotifyDialog(self.ctx, self.window())
        dialog.exec()

    def on_app_setting_clicked(self, app_id: str) -> None:
        """处理应用设置按钮被点击，委托给 app_setting_manager"""
        window = self.window()
        if not isinstance(window, MainAppWindowBase):
            return
        target = self._find_app_card_setting_btn(app_id)
        if target is None:
            return
        window.app_setting_manager.show_app_setting(
            app_id=app_id,
            parent=self,
            group_id=application_const.DEFAULT_GROUP_ID,
            target=target,
        )

    def _update_setting_btn_visibility(self) -> None:
        """根据 app_setting_manager 的注册信息，显示或隐藏卡片的设置按钮"""
        window = self.window()
        if not isinstance(window, MainAppWindowBase):
            return
        settable = window.app_setting_manager.settable_app_ids
        for card in self.app_run_list._app_cards:
            card.setting_btn.setVisible(card.app.app_id in settable)

    def _find_app_card_setting_btn(self, app_id: str):
        """找到对应 app_id 的卡片的设置按钮"""
        for card in self.app_run_list._app_cards:
            if card.app.app_id == app_id:
                return card.setting_btn
        return None
