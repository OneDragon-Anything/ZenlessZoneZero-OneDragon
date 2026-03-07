from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PlainTextEdit, PrimaryPushButton, PushButton, SubtitleLabel

from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_context import ContextKeyboardEventEnum
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext


class AiAssistantInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.state_text = SubtitleLabel('点击“启动”后启动MCP并生成可复制的 JSON')
        layout.addWidget(self.state_text)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(btn_row)

        self.generate_btn = PrimaryPushButton(
            text=f'启动 {self.ctx.key_start_running.upper()}',
            icon=FluentIcon.PLAY
        )
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        btn_layout.addWidget(self.generate_btn)

        self.stop_btn = PushButton(
            text=f'停止 {self.ctx.key_stop_running.upper()}',
            icon=FluentIcon.CLOSE
        )
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        btn_layout.addWidget(self.stop_btn)

        self.copy_btn = PushButton(text='复制 JSON', icon=FluentIcon.COPY)
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        self.copy_btn.setDisabled(True)
        btn_layout.addWidget(self.copy_btn)

        self.json_edit = PlainTextEdit()
        self.json_edit.setReadOnly(True)
        self.json_edit.setPlaceholderText('MCP JSON 将显示在这里')
        self.json_edit.setMinimumHeight(240)
        layout.addWidget(self.json_edit)

        self.log_card = LogDisplayCard()
        self.log_card.setPlaceholderText('日志输出（参照自动战斗日志）')
        self.log_card.setMinimumHeight(220)
        layout.addWidget(self.log_card)

        VerticalScrollInterface.__init__(
            self,
            content_widget=content_widget,
            object_name='ai_assistant_interface',
            nav_text_cn='AI辅助',
            nav_icon=FluentIcon.ROBOT,
            parent=parent,
        )

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)
        self.log_card.start()
        self._refresh_status()

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
        self.ctx.unlisten_all_event(self)
        self.log_card.stop()

    def _refresh_status(self) -> None:
        if self.ctx.is_mcp_service_running():
            self.state_text.setText('MCP服务运行中，可复制 JSON')
            self.copy_btn.setDisabled(False)
        else:
            self.state_text.setText('MCP服务未启动')
            self.copy_btn.setDisabled(True)

    def _on_generate_clicked(self) -> None:
        try:
            self.ctx.start_mcp_service()
            config_json = self.ctx.get_mcp_client_config_json()
            self.json_edit.setPlainText(config_json)
            self._refresh_status()
            self.show_info_bar(title='生成成功', content='MCP JSON 已准备好')
        except Exception as e:
            self.copy_btn.setDisabled(True)
            self.json_edit.setPlainText('')
            self.state_text.setText('生成失败')
            self.show_info_bar(title='生成失败', content=str(e))

    def _on_stop_clicked(self) -> None:
        try:
            self.ctx.stop_mcp_service()
            self._refresh_status()
            self.show_info_bar(title='已停止', content='MCP服务与自动战斗已停止')
        except Exception as e:
            self.show_info_bar(title='停止失败', content=str(e))

    def _on_key_press(self, event: ContextEventItem) -> None:
        key: str = event.data
        if key == self.ctx.key_start_running and not self.ctx.is_mcp_service_running():
            self._on_generate_clicked()
        elif key == self.ctx.key_stop_running and self.ctx.is_mcp_service_running():
            self._on_stop_clicked()

    def _on_copy_clicked(self) -> None:
        text = self.json_edit.toPlainText().strip()
        if not text:
            self.show_info_bar(title='无可复制内容', content='请先点击“启动生成”')
            return
        QApplication.clipboard().setText(text)
        self.show_info_bar(title='已复制', content='MCP JSON 已复制到剪贴板')
