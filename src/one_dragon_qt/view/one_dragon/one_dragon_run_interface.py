from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import FluentIcon, SettingCardGroup, SubtitleLabel, PrimaryPushButton, PushButton, SingleDirectionScrollArea
from typing import List, Optional

from one_dragon.base.config.one_dragon_app_config import OneDragonAppConfig
from one_dragon.base.config.one_dragon_config import InstanceRun, AfterDoneOpEnum
from one_dragon.base.operation.application_base import Application, ApplicationEventId
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_app import OneDragonApp
from one_dragon.base.operation.one_dragon_context import OneDragonContext, ContextKeyboardEventEnum, \
    ContextInstanceEventEnum
from one_dragon_qt.view.app_run_interface import AppRunner
from one_dragon_qt.view.context_event_signal import ContextEventSignal
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.setting_card.app_run_card import AppRunCard
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.notify_dialog import NotifyDialog
from one_dragon.utils import cmd_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class OneDragonRunInterface(VerticalScrollInterface):

    run_all_apps_signal = Signal()

    def __init__(self, ctx: OneDragonContext,
                 nav_text_cn: str = '一条龙运行',
                 object_name: str = 'one_dragon_run_interface',
                 need_multiple_instance: bool = True,
                 need_after_done_opt: bool = True,
                 help_url: Optional[str] = None, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name=object_name,
            parent=parent,
            nav_text_cn=nav_text_cn
        )

        self.ctx: OneDragonContext = ctx
        self._app_run_cards: List[AppRunCard] = []
        self._context_event_signal = ContextEventSignal()
        self.help_url: str = help_url  # 使用说明的链接
        self.need_multiple_instance: bool = need_multiple_instance  # 是否需要多实例
        self.need_after_done_opt: bool = need_after_done_opt  # 结束后

    def get_content_widget(self) -> QWidget:
        """
        子界面内的内容组件 由子类实现
        :return:
        """
        content_widget = QWidget()
        # 创建 QVBoxLayout 作为主布局
        main_layout = QVBoxLayout(content_widget)

        # 创建 QHBoxLayout 作为中间布局
        horizontal_layout = QHBoxLayout()

        # 将 QVBoxLayouts 加入 QHBoxLayout
        horizontal_layout.addLayout(self._get_left_layout(), stretch=1)
        horizontal_layout.addLayout(self._get_right_layout(), stretch=1)

        # 设置 QHBoxLayout 的间距和边框
        horizontal_layout.setSpacing(10)
        horizontal_layout.setContentsMargins(0, 0, 0, 0)

        # 设置伸缩因子，让 QHBoxLayout 占据空间
        main_layout.addLayout(horizontal_layout, stretch=1)

        self.app_runner = AppRunner(self.ctx)
        self.app_runner.state_changed.connect(self.on_context_state_changed)

        return content_widget

    def _get_left_layout(self) -> QVBoxLayout:
        """
        左边的布局
        :return:
        """
        layout = QVBoxLayout()

        scroll_area = SingleDirectionScrollArea()
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 16, 0)

        self.app_card_group = SettingCardGroup(gt('任务列表'))
        scroll_layout.addWidget(self.app_card_group)
        scroll_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)

        return layout

    def _get_right_layout(self) -> QVBoxLayout:
        """
        右边的布局
        :return:
        """
        layout = QVBoxLayout()
        layout.setSpacing(5)

        run_group = SettingCardGroup(gt('运行设置'))
        layout.addWidget(run_group)

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

        self.state_text = SubtitleLabel()
        self.state_text.setText('%s %s' % (gt('当前状态'), self.ctx.context_running_status_text))
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.state_text)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(5)
        layout.addLayout(btn_row)

        self.start_btn = PrimaryPushButton(
            text='%s %s' % (gt('开始'), self.ctx.key_start_running.upper()),
            icon=FluentIcon.PLAY,
        )
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_row.addWidget(self.start_btn, stretch=1)

        self.stop_btn = PushButton(
            text='%s %s' % (gt('停止'), self.ctx.key_stop_running.upper()),
            icon=FluentIcon.CLOSE
        )
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        btn_row.addWidget(self.stop_btn, stretch=1)

        self.log_card = LogDisplayCard()
        layout.addWidget(self.log_card, stretch=1)

        return layout

    def _init_app_list(self) -> None:
        """
        初始化应用列表
        :return:
        """
        if not self.ctx.is_context_stop:  # 不是停止状态不更新
            return
        self.app_list = self.get_one_dragon_app().get_one_dragon_apps_in_order()
        app_run_list = self.get_app_run_list()

        if len(self._app_run_cards) > 0:  # 之前已经添加了组件了 这次只是调整顺序
            for idx, app in enumerate(self.app_list):
                self._app_run_cards[idx].set_app(app)
                self._app_run_cards[idx].set_switch_on(app.app_id in app_run_list)
        else:
            for app in self.app_list:
                app_run_card = AppRunCard(app, switch_on=app.app_id in app_run_list)
                self._app_run_cards.append(app_run_card)
                self.app_card_group.addSettingCard(app_run_card)
                app_run_card.update_display()

                app_run_card.move_up.connect(self.on_app_card_move_up)
                app_run_card.run.connect(self._on_app_card_run)
                app_run_card.switched.connect(self.on_app_switch_run)

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self._init_app_list()
        self.notify_switch.init_with_adapter(self.ctx.notify_config.get_prop_adapter('enable_notify'))

        self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)
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
        self.run_all_apps_signal.connect(self.run_all_apps)

        if self.ctx.signal.start_onedragon:
            self.ctx.signal.start_onedragon = False
            self.run_all_apps_signal.emit()

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
        self.ctx.unlisten_all_event(self)
        self._context_event_signal.instance_changed.disconnect(self._on_instance_changed)

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

    def run_app(self, app: Application) -> None:
        self.app_runner.app = app
        if app.run_record is not None:
            app.run_record.check_and_update_status()
        self.app_runner.start()

    def run_all_apps(self) -> None:
        self.run_app(self.get_one_dragon_app())

    def _on_start_clicked(self) -> None:
        self.run_all_apps()

    def _on_stop_clicked(self) -> None:
        self.ctx.stop_running()

    def _on_key_press(self, event: ContextEventItem) -> None:
        """
        按键监听
        """
        key: str = event.data
        if key == self.ctx.key_start_running and self.ctx.is_context_stop:
            self.run_all_apps()

    def on_context_state_changed(self) -> None:
        """
        按运行状态更新显示
        :return:
        """
        if self.ctx.is_context_running:
            text = gt('暂停')
            icon = FluentIcon.PAUSE
            self.log_card.start()  # 开始日志更新
        elif self.ctx.is_context_pause:
            text = gt('继续')
            icon = FluentIcon.PLAY
            self.log_card.pause()  # 暂停日志更新
        else:
            text = gt('开始')
            icon = FluentIcon.PLAY
            self.log_card.stop()  # 停止日志更新

        self.start_btn.setText('%s %s' % (text, self.ctx.key_start_running.upper()))
        self.start_btn.setIcon(icon)
        self.state_text.setText('%s %s' % (gt('当前状态'), self.ctx.context_running_status_text))

        for app_card in self._app_run_cards:
            app_card.update_display()

        if self.ctx.is_context_stop and self.need_after_done_opt:
            if self.ctx.one_dragon_config.after_done == AfterDoneOpEnum.SHUTDOWN.value.value:
                cmd_utils.shutdown_sys(60)
            elif self.ctx.one_dragon_config.after_done == AfterDoneOpEnum.CLOSE_GAME.value.value:
                self.ctx.controller.close_game()

    def _on_app_state_changed(self, event) -> None:
        for app_card in self._app_run_cards:
            app_card.update_display()

    def on_app_card_move_up(self, app_id: str) -> None:
        """
        将该应用往上调整一位
        :param app_id:
        :return:
        """
        self.get_one_dragon_app_config().move_up_app(app_id)
        self._init_app_list()

    def _on_app_card_run(self, app_id: str) -> None:
        """
        运行某个特殊的应用
        :param app_id:
        :return:
        """
        for app in self.app_list:
            if app.app_id == app_id:
                self.run_app(app)

    def on_app_switch_run(self, app_id: str, value: bool) -> None:
        """
        应用运行状态切换
        :param app_id:
        :param value:
        :return:
        """
        self.get_one_dragon_app_config().set_app_run(app_id, value)

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
        self.app_list = self.get_one_dragon_app().get_one_dragon_apps_in_order()
        for idx, app in enumerate(self.app_list):
            self._app_run_cards[idx].set_app(app)
            app_run_list = self.get_app_run_list()
            self._app_run_cards[idx].set_switch_on(app.app_id in app_run_list)

    def _on_instance_run_changed(self, idx: int, value: str) -> None:
        self.ctx.one_dragon_config.instance_run = value

    def get_one_dragon_app(self) -> OneDragonApp:
        pass

    def get_app_run_list(self) -> List[str]:
        """
        获取需要运行的app id列表
        :return:
        """
        return self.get_one_dragon_app_config().app_run_list

    def get_one_dragon_app_config(self) -> OneDragonAppConfig:
        return self.ctx.one_dragon_app_config

    def _init_notify_switch(self) -> None:
        pass

    def _on_notify_setting_clicked(self) -> None:
        self.show_notify_dialog()

    def show_notify_dialog(self) -> None:
        """
        显示通知设置对话框。配置更新由对话框内部处理。
        """
        dialog = NotifyDialog(self, self.ctx)
        dialog.exec()
