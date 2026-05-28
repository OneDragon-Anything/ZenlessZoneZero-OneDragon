"""AI 助手内联聊天面板，嵌入主页左侧容器，向上展开"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, Theme, qconfig

from one_dragon_qt.services.ai_assistant_service import AiAssistantService


class _ChatMessage(QWidget):
    """单条聊天消息，全宽平铺"""

    def __init__(self, text: str, is_user: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.is_user = is_user

        is_dark = qconfig.theme == Theme.DARK

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(4)

        prefix = QLabel('你' if is_user else 'AI')
        prefix.setFixedWidth(24)
        prefix.setFont(QFont('Microsoft YaHei', 8, QFont.Weight.Bold))
        prefix_fg = '#6699CC' if is_user else ('#88CC88' if is_dark else '#44AA44')
        prefix.setStyleSheet(f'color: {prefix_fg}; border: none;')
        layout.addWidget(prefix)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setFont(QFont('Microsoft YaHei', 9))
        fg = '#E0E0E0' if is_dark else '#1A1A1A'
        body.setStyleSheet(f'color: {fg}; border: none;')
        layout.addWidget(body, stretch=1)

        self._body = body
        self._fg = fg

    def update_text(self, text: str) -> None:
        self._body.setText(text)


class AiChatPanel(QWidget):
    """AI 助手内联面板，嵌入左侧容器，点击触发栏向上展开聊天区域"""

    send_message = Signal(str)
    # 线程安全信号：后台线程通过这些信号把回调转发到主线程
    _chunk_received = Signal(str)
    _reply_done = Signal(str)
    _reply_error = Signal(str)

    def __init__(self, service: AiAssistantService, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._is_loading = False
        self._expanded = False
        self._current_msg: _ChatMessage | None = None
        self._current_text: str = ''
        self._init_ui()

        # 连接线程安全信号 → 主线程 UI 更新
        self._chunk_received.connect(self._handle_chunk)
        self._reply_done.connect(self._handle_done)
        self._reply_error.connect(self._handle_error)

    def _init_ui(self) -> None:
        self.setFixedWidth(589)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Minimum,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # 聊天区域（默认隐藏，展开时显示在上方）
        self._chat_container = QWidget()
        chat_layout = QVBoxLayout(self._chat_container)
        chat_layout.setContentsMargins(12, 8, 12, 8)
        chat_layout.setSpacing(4)

        # 聊天标题栏
        chat_header = QHBoxLayout()
        chat_header.setSpacing(8)

        title = QLabel('AI 助手')
        title.setFont(QFont('Microsoft YaHei', 9, QFont.Weight.Bold))
        chat_header.addWidget(title)
        chat_header.addStretch()

        clear_btn = QPushButton('清除')
        clear_btn.setFixedSize(36, 20)
        clear_btn.setFont(QFont('Microsoft YaHei', 7))
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._on_clear)
        chat_header.addWidget(clear_btn)

        chat_layout.addLayout(chat_header)

        # 聊天消息区
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setFixedHeight(260)

        self._scroll_widget = QWidget()
        self._chat_layout = QVBoxLayout(self._scroll_widget)
        self._chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._chat_layout.setSpacing(0)
        self._chat_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_layout.addStretch()
        self._scroll_area.setWidget(self._scroll_widget)
        self._apply_scroll_style()
        chat_layout.addWidget(self._scroll_area)

        # 输入栏
        input_bar = QHBoxLayout()
        input_bar.setSpacing(6)

        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText('输入问题，问 AI 助手...')
        self._input_field.setFont(QFont('Microsoft YaHei', 9))
        self._input_field.returnPressed.connect(self._on_send)
        input_bar.addWidget(self._input_field)

        self._send_btn = QPushButton()
        self._send_btn.setFixedSize(28, 28)
        self._send_btn.setIcon(FluentIcon.SEND.icon())
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._on_send)
        input_bar.addWidget(self._send_btn)

        chat_layout.addLayout(input_bar)
        self._apply_chat_style()

        self._chat_container.hide()
        root.addWidget(self._chat_container)

        # 触发栏（始终可见）
        self._trigger_bar = QWidget()
        self._trigger_bar.setFixedHeight(32)
        self._trigger_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        trigger_layout = QHBoxLayout(self._trigger_bar)
        trigger_layout.setContentsMargins(12, 4, 12, 4)

        trigger_icon = QLabel('AI')
        trigger_icon.setFont(QFont('Microsoft YaHei', 8, QFont.Weight.Bold))
        trigger_layout.addWidget(trigger_icon)

        trigger_text = QLabel('问 AI 助手')
        trigger_text.setFont(QFont('Microsoft YaHei', 8))
        trigger_layout.addWidget(trigger_text)
        trigger_layout.addStretch()

        self._toggle_icon = QLabel('▼')
        self._toggle_icon.setFont(QFont('Microsoft YaHei', 7))
        trigger_layout.addWidget(self._toggle_icon)

        self._apply_trigger_style()
        self._trigger_bar.mousePressEvent = lambda e: self.toggle()
        root.addWidget(self._trigger_bar)

    def _apply_trigger_style(self) -> None:
        is_dark = qconfig.theme == Theme.DARK
        bg = 'rgba(18, 20, 30, 170)' if is_dark else 'rgba(22, 24, 35, 175)'
        fg = 'rgba(200, 200, 205, 180)' if is_dark else 'rgba(150, 150, 155, 180)'
        border = 'rgba(255,255,255,25)' if is_dark else 'rgba(255,255,255,20)'

        self._trigger_bar.setStyleSheet(
            f'QWidget {{ background-color: {bg}; color: {fg}; '
            f'border: 1px solid {border}; border-radius: 8px; }}'
            f'QLabel {{ color: {fg}; border: none; }}'
        )

    def _apply_chat_style(self) -> None:
        is_dark = qconfig.theme == Theme.DARK
        bg = 'rgba(18, 20, 30, 190)' if is_dark else 'rgba(22, 24, 35, 195)'
        border = 'rgba(255,255,255,25)' if is_dark else 'rgba(255,255,255,20)'
        fg = '#E0E0E0' if is_dark else '#1A1A1A'
        input_bg = 'rgba(40, 42, 55, 200)' if is_dark else 'rgba(245, 245, 245, 230)'
        btn_hover = 'rgba(70, 70, 75, 150)' if is_dark else 'rgba(230, 230, 230, 150)'

        self._chat_container.setStyleSheet(
            f'QWidget {{ background-color: {bg}; color: {fg}; '
            f'border: 1px solid {border}; border-radius: 8px; }}'
            f'QLineEdit {{ background-color: {input_bg}; color: {fg}; '
            f'border: 1px solid {border}; border-radius: 14px; '
            f'padding: 4px 10px; }}'
            f'QPushButton {{ background-color: transparent; color: {fg}; '
            f'border: none; border-radius: 4px; }}'
            f'QPushButton:hover {{ background-color: {btn_hover}; }}'
            f'QLabel {{ color: {fg}; border: none; }}'
        )

    def _apply_scroll_style(self) -> None:
        self._scroll_area.setStyleSheet(
            'QScrollArea { border: none; background: transparent; }'
            'QScrollBar:vertical { width: 4px; background: transparent; }'
            'QScrollBar::handle:vertical { background: rgba(150,150,150,80);'
            '  border-radius: 2px; }'
        )

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        """切换展开/收起"""
        self._expanded = not self._expanded
        if self._expanded:
            self._chat_container.show()
            self._toggle_icon.setText('▲')
            self._input_field.setFocus()
        else:
            self._chat_container.hide()
            self._toggle_icon.setText('▼')
        self.updateGeometry()

    def _on_send(self) -> None:
        """发送消息"""
        if self._is_loading:
            return
        text = self._input_field.text().strip()
        if not text:
            return
        self._input_field.clear()

        self._add_message(text, is_user=True)

        self._current_text = ''
        self._current_msg = _ChatMessage('...', is_user=False)
        self._insert_before_stretch(self._current_msg)
        self._scroll_to_bottom()

        self._is_loading = True
        self.send_message.emit(text)

    # ---- 线程安全回调（从后台线程调用，通过信号转发到主线程）----

    def on_chunk(self, chunk: str) -> None:
        """流式接收片段（可从后台线程调用）"""
        self._chunk_received.emit(chunk)

    def on_done(self, reply: str) -> None:
        """回复完成（可从后台线程调用）"""
        self._reply_done.emit(reply)

    def on_error(self, error: str) -> None:
        """回复出错（可从后台线程调用）"""
        self._reply_error.emit(error)

    # ---- 主线程 UI 更新（由信号触发，保证在主线程执行）----

    def _handle_chunk(self, chunk: str) -> None:
        """主线程：处理流式片段"""
        self._current_text += chunk
        if self._current_msg is not None:
            self._current_msg.update_text(
                self._current_text if self._current_text else '...'
            )
        self._scroll_to_bottom()

    def _handle_done(self, reply: str) -> None:
        """主线程：处理回复完成"""
        self._is_loading = False
        self._current_msg = None
        self._current_text = ''

    def _handle_error(self, error: str) -> None:
        """主线程：处理回复出错"""
        self._is_loading = False
        if self._current_msg is not None:
            self._current_msg.update_text(f'[错误] {error}')
            self._current_msg._body.setStyleSheet('color: #FF6B6B; border: none;')
        self._current_msg = None
        self._current_text = ''

    def _on_clear(self) -> None:
        """清除对话历史"""
        self._service.clear_history()
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _add_message(self, text: str, is_user: bool) -> None:
        msg = _ChatMessage(text, is_user=is_user)
        self._insert_before_stretch(msg)
        self._scroll_to_bottom()

    def _insert_before_stretch(self, widget: QWidget) -> None:
        count = self._chat_layout.count()
        self._chat_layout.insertWidget(count - 1, widget)

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(
            50,
            lambda: self._scroll_area.verticalScrollBar()
            .setValue(self._scroll_area.verticalScrollBar().maximum()),
        )
