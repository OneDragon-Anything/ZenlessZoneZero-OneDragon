from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import FluentIconBase, PrimaryPushButton, FluentIcon, PushButton, SubtitleLabel
from typing import Union, Optional

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_context import ContextKeyboardEventEnum, ContextRunningStateEventEnum, \
    OneDragonContext
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class AppRunner(QThread):

    state_changed = Signal()

    def __init__(self, ctx: OneDragonContext, app: Optional[Application] = None):
        super().__init__()
        self.ctx: OneDragonContext = ctx
        self.app: Application = app

    def run(self):
        """
        运行 最后发送结束信号
        :return:
        """
        self.ctx.listen_event(ContextRunningStateEventEnum.START_RUNNING.value, self._on_state_changed)
        self.ctx.listen_event(ContextRunningStateEventEnum.PAUSE_RUNNING.value, self._on_state_changed)
        self.ctx.listen_event(ContextRunningStateEventEnum.STOP_RUNNING.value, self._on_state_changed)
        self.ctx.listen_event(ContextRunningStateEventEnum.RESUME_RUNNING.value, self._on_state_changed)

        self.app.execute()

        self.ctx.unlisten_all_event(self)

    def _on_state_changed(self, ignored) -> None:
        """
        运行状态改变
        :return:
        """
        self.state_changed.emit()


class AppRunInterface(VerticalScrollInterface):

    def __init__(self,
                 ctx: OneDragonContext,
                 object_name: str,
                 nav_text_cn: str,
                 nav_icon: Union[FluentIconBase, QIcon, str] = None,
                 parent=None,
                 ):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name=object_name,
            nav_text_cn=nav_text_cn,
            nav_icon=nav_icon,
            parent=parent
        )
        self.ctx: OneDragonContext = ctx

    def get_content_widget(self) -> QWidget:
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        widget_at_top = self.get_widget_at_top()
        if widget_at_top is not None:
            content_layout.addWidget(widget_at_top)

        self.state_text = SubtitleLabel()
        self.state_text.setText('%s %s' % (gt('当前状态'), self.ctx.context_running_status_text))
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        content_layout.addWidget(self.state_text)

        # 按钮行
        btn_row_widget = QWidget()
        btn_row_layout = QHBoxLayout(btn_row_widget)
        content_layout.addWidget(btn_row_widget)

        self.start_btn = PrimaryPushButton(
            text='%s %s' % (gt('开始'), self.ctx.key_start_running.upper()),
            icon=FluentIcon.PLAY,
        )
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_row_layout.addWidget(self.start_btn)

        self.stop_btn = PushButton(
            text='%s %s' % (gt('停止'), self.ctx.key_stop_running.upper()),
            icon=FluentIcon.CLOSE
        )
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        btn_row_layout.addWidget(self.stop_btn)

        self.log_card = LogDisplayCard()
        content_layout.addWidget(self.log_card)

        self.app_runner = AppRunner(self.ctx)
        self.app_runner.state_changed.connect(self.on_context_state_changed)

        widget_at_bottom = self.get_widget_at_bottom()
        if widget_at_bottom is not None:
            content_layout.addWidget(widget_at_bottom)

        content_layout.setStretch(content_layout.count() - 1, 1)

        return content_widget

    def get_widget_at_top(self) -> QWidget:
        pass

    def get_widget_at_bottom(self) -> QWidget:
        pass

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
        self.ctx.unlisten_all_event(self)

    def _on_key_press(self, event: ContextEventItem) -> None:
        """
        按键监听
        """
        key: str = event.data
        if key == self.ctx.key_start_running and self.ctx.is_context_stop:
            self._on_start_clicked()

    def run_app(self) -> None:
        """
        运行应用
        """
        if self.app_runner.isRunning():
            log.error('已有应用在运行中')
            return
        app = self.get_app()
        if app is None:
            log.error('未提供对应应用')
            return
        if app.run_record is not None:
            app.run_record.check_and_update_status()
        self.app_runner.app = app
        self.app_runner.start()

    def get_app(self) -> Application:
        """
        获取本次运行的app 由子类实现
        由
        :return:
        """
        pass

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

    def _on_start_clicked(self) -> None:
        if self.ctx.is_context_stop:
            self.run_app()
        elif self.ctx.is_context_running:
            self.ctx.switch_context_pause_and_run()
        elif self.ctx.is_context_pause:
            self.ctx.switch_context_pause_and_run()

    def _on_stop_clicked(self) -> None:
        self.ctx.stop_running()
