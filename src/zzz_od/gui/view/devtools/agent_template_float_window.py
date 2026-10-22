from __future__ import annotations

from cv2.typing import MatLike
from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    StrongBodyLabel,
    ToolTipFilter,
    TransparentToolButton,
    isDarkTheme,
)

from one_dragon.utils.i18_utils import gt
from zzz_od.gui.view.devtools.agent_template_widgets import ImageSlot


class AgentTemplateFloatWindow(QWidget):
    """置顶悬浮窗，不抢占游戏焦点，只操作当前步骤。"""

    capture_clicked = Signal()
    next_clicked = Signal()
    close_clicked = Signal()
    moved = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        self.progress_label = CaptionLabel()
        self.name_label = StrongBodyLabel()
        self.name_label.setMinimumWidth(96)
        text_col.addWidget(self.progress_label)
        text_col.addWidget(self.name_label)
        layout.addLayout(text_col)

        self.preview = ImageSlot(72, 40)
        layout.addWidget(self.preview)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(4)
        self.btn_capture = self._tool_button(FluentIcon.CAMERA, gt('截图'))
        self.btn_capture.clicked.connect(self.capture_clicked)
        self.btn_next = self._tool_button(FluentIcon.CHEVRON_RIGHT, gt('下一步'))
        self.btn_next.clicked.connect(self.next_clicked)
        self.btn_close = self._tool_button(FluentIcon.CLOSE, gt('关闭'))
        self.btn_close.clicked.connect(self.close_clicked)
        for btn in (self.btn_capture, self.btn_next, self.btn_close):
            buttons.addWidget(btn)
        layout.addLayout(buttons)

    def _tool_button(self, icon: FluentIcon, tip: str) -> TransparentToolButton:
        btn = TransparentToolButton(icon)
        btn.setToolTip(tip)
        btn.setAccessibleName(tip)
        btn.installEventFilter(ToolTipFilter(btn))
        return btn

    def set_step(self, index: int, total: int, name: str, preview: MatLike | None,
                 can_next: bool, is_last: bool) -> None:
        """最后一步的按钮改为回到主界面，保存只在主界面进行。"""
        self.progress_label.setText(f'{index + 1} / {total}')
        self.name_label.setText(name)
        self.preview.set_image(preview)
        tip = gt('回到主界面') if is_last else gt('下一步')
        self.btn_next.setIcon(FluentIcon.HOME if is_last else FluentIcon.CHEVRON_RIGHT)
        self.btn_next.setToolTip(tip)
        self.btn_next.setAccessibleName(tip)
        self.btn_next.setEnabled(can_next)
        self.adjustSize()

    def show_at(self, x: int, y: int) -> None:
        """显示在指定位置，位置无效时显示在主屏右上角。"""
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        if not screen.contains(QPoint(x, y)):
            x = screen.right() - self.width() - 24
            y = screen.top() + 24
        self.move(x, y)
        self.show()

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        if isDarkTheme():
            painter.fillPath(path, QColor(44, 44, 44, 245))
            painter.setPen(QColor(255, 255, 255, 24))
        else:
            painter.fillPath(path, QColor(252, 252, 252, 245))
            painter.setPen(QColor(0, 0, 0, 24))
        painter.drawPath(path)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self.moved.emit(self.x(), self.y())
