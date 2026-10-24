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
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    FluentIcon,
    StrongBodyLabel,
    ToolTipFilter,
    TransparentToolButton,
    isDarkTheme,
    themeColor,
)

from one_dragon.utils.i18_utils import gt
from zzz_od.gui.view.devtools.agent_template_widgets import ImageSlot, KeyCapRow


class SegmentedProgress(QWidget):
    """分段进度条，每段对应一个模板，已截图的段填充强调色。"""

    def __init__(self, count: int, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self.setFixedHeight(4)
        self._done: list[bool] = [False] * count

    def set_done(self, done: list[bool]) -> None:
        self._done = done
        self.update()

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        gap = 4
        count = len(self._done)
        width = (self.width() - gap * (count - 1)) / count
        idle = QColor(255, 255, 255, 40) if isDarkTheme() else QColor(0, 0, 0, 30)
        for idx, done in enumerate(self._done):
            painter.setBrush(themeColor() if done else idle)
            painter.drawRoundedRect(QRectF(idx * (width + gap), 0, width, self.height()), 2, 2)


class FloatThumb(CardWidget):
    """展开后的一个模板缩略图，选中时显示强调色边框。"""

    WIDTH: int = 96

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        CardWidget.__init__(self, parent)
        self._selected: bool = False
        self.setFixedWidth(self.WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.image = ImageSlot(self.WIDTH - 12, 48)
        layout.addWidget(self.image)
        layout.addWidget(CaptionLabel(name), alignment=Qt.AlignmentFlag.AlignHCenter)
        self.caps = KeyCapRow()
        layout.addWidget(self.caps, alignment=Qt.AlignmentFlag.AlignHCenter)

    def set_state(self, image: MatLike | None, keys: list[str], selected: bool) -> None:
        self.image.set_image(image)
        self.caps.set_keys(keys)
        self._selected = selected
        self.update()

    def paintEvent(self, e: QPaintEvent) -> None:
        CardWidget.paintEvent(self, e)
        if not self._selected:
            return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        pen = painter.pen()
        pen.setColor(themeColor())
        pen.setWidthF(2)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), self.borderRadius, self.borderRadius)


class AgentTemplateFloatWindow(QWidget):
    """置顶悬浮窗，不抢占游戏焦点，显示当前模板和完成进度，展开后显示全部模板。"""

    switch_clicked = Signal()
    close_clicked = Signal()
    expand_toggled = Signal(bool)
    template_clicked = Signal(int)
    moved = Signal(int, int)

    def __init__(self, template_names: list[str], parent: QWidget | None = None) -> None:
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
        self._template_names: list[str] = template_names
        self._expanded: bool = False
        self._expand_text: str = ''

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)
        self.preview = ImageSlot(72, 48)
        content.addWidget(self.preview)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(4)
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)
        self.name_label = StrongBodyLabel()
        name_row.addWidget(self.name_label)
        self.name_caps = KeyCapRow()
        name_row.addWidget(self.name_caps)
        name_row.addStretch(1)
        info_col.addLayout(name_row)
        self.count_label = CaptionLabel()
        info_col.addWidget(self.count_label)
        content.addLayout(info_col, stretch=1)

        self.btn_expand = self._tool_button(FluentIcon.DOWN, '')
        self.btn_expand.clicked.connect(lambda: self.set_expanded(not self._expanded, emit=True))
        self.btn_switch = self._tool_button(FluentIcon.SYNC, gt('切换窗口'))
        self.btn_switch.clicked.connect(self.switch_clicked)
        self.btn_close = self._tool_button(FluentIcon.CLOSE, gt('关闭'))
        self.btn_close.clicked.connect(self.close_clicked)
        for btn in (self.btn_expand, self.btn_switch, self.btn_close):
            content.addWidget(btn, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(content)

        self.progress = SegmentedProgress(len(template_names))
        layout.addWidget(self.progress)

        self.thumb_area = QWidget()
        grid = QGridLayout(self.thumb_area)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        self.thumbs: list[FloatThumb] = []
        for idx, name in enumerate(template_names):
            thumb = FloatThumb(gt(name))
            thumb.clicked.connect(lambda i=idx: self.template_clicked.emit(i))
            grid.addWidget(thumb, idx // 3, idx % 3)
            self.thumbs.append(thumb)
        self.thumb_area.hide()
        layout.addWidget(self.thumb_area)
        self.setMinimumWidth(320)

    def _tool_button(self, icon: FluentIcon, tip: str) -> TransparentToolButton:
        btn = TransparentToolButton(icon)
        btn.setToolTip(tip)
        btn.setAccessibleName(tip)
        btn.installEventFilter(ToolTipFilter(btn))
        return btn

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, emit: bool = False) -> None:
        self._expanded = expanded
        self.thumb_area.setVisible(expanded)
        self.btn_expand.setIcon(FluentIcon.UP if expanded else FluentIcon.DOWN)
        self._update_expand_tip()
        self.layout().activate()
        self.adjustSize()
        if emit:
            self.expand_toggled.emit(expanded)

    def _update_expand_tip(self) -> None:
        tip = gt('收起悬浮窗') if self._expanded else gt('展开悬浮窗')
        if self._expand_text:
            tip = f'{tip} ({self._expand_text})'
        self.btn_expand.setToolTip(tip)
        self.btn_expand.setAccessibleName(tip)

    def set_state(self, current_idx: int, crops: list[MatLike | None], keys: list[list[str]],
                  switch_text: str, expand_text: str) -> None:
        """
        :param current_idx: 主界面当前选中的模板
        :param crops: 每个模板的裁剪结果 没有截图时为 None
        :param keys: 每个模板的截图快捷键
        """
        self.preview.set_image(crops[current_idx])
        self.name_label.setText(gt(self._template_names[current_idx]))
        self.name_caps.set_keys(keys[current_idx])
        done = [crop is not None for crop in crops]
        self.count_label.setText(f'{sum(done)} / {len(done)}')
        self.progress.set_done(done)
        for idx, thumb in enumerate(self.thumbs):
            thumb.set_state(crops[idx], keys[idx], idx == current_idx)

        tip = f'{gt("切换窗口")} ({switch_text})' if switch_text else gt('切换窗口')
        self.btn_switch.setToolTip(tip)
        self.btn_switch.setAccessibleName(tip)
        self._expand_text = expand_text
        self._update_expand_tip()
        self.layout().activate()
        self.adjustSize()

    def show_at(self, x: int, y: int) -> None:
        """显示在指定位置，位置不在任何屏幕内时显示在主屏右上角。"""
        self.adjustSize()
        if QGuiApplication.screenAt(QPoint(x, y)) is None:
            screen = QGuiApplication.primaryScreen().availableGeometry()
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
