from __future__ import annotations

import numpy as np
from cv2.typing import MatLike
from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    IconWidget,
    InfoBarIcon,
    PushButton,
    RoundMenu,
    ToolTipFilter,
    TransparentToolButton,
    getFont,
    isDarkTheme,
    themeColor,
)

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.cv2_image import Cv2Image


class ImageSlot(QWidget):
    """固定大小的图片位，保持比例居中显示，无图时显示占位图标。"""

    def __init__(self, width: int, height: int, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self.setFixedSize(width, height)
        self._pixmap: QPixmap | None = None

    def set_image(self, image: MatLike | None) -> None:
        self._pixmap = None if image is None else QPixmap.fromImage(Cv2Image(np.ascontiguousarray(image)))
        self.update()

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        dark = isDarkTheme()
        painter.fillPath(path, QColor(255, 255, 255, 10) if dark else QColor(0, 0, 0, 6))

        if self._pixmap is not None and not self._pixmap.isNull():
            ratio = self.devicePixelRatioF()
            scaled = self._pixmap.scaled(
                int(self.width() * ratio), int(self.height() * ratio),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(ratio)
            w = scaled.width() / ratio
            h = scaled.height() / ratio
            painter.setClipPath(path)
            painter.drawPixmap(QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h), scaled, QRectF(scaled.rect()))
            painter.setClipping(False)
        else:
            size = min(24, self.height() // 2)
            painter.setOpacity(0.45)
            FluentIcon.PHOTO.render(painter, QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size))
            painter.setOpacity(1)

        painter.setPen(QColor(255, 255, 255, 20) if dark else QColor(0, 0, 0, 18))
        painter.drawPath(path)


class StepThumb(CardWidget):
    """一个模板的缩略图，点击打开该模板，下方按钮直接截图，选中时显示强调色边框。"""

    WIDTH: int = 152

    capture_clicked = Signal()

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        CardWidget.__init__(self, parent)
        self._selected: bool = False
        self.setFixedWidth(self.WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.image = ImageSlot(self.WIDTH - 16, 64)
        layout.addWidget(self.image)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(4)
        name_row.addStretch(1)
        self.done_icon = IconWidget(FluentIcon.COMPLETED)
        self.done_icon.setFixedSize(12, 12)
        self.done_icon.hide()
        name_row.addWidget(self.done_icon)
        name_row.addWidget(CaptionLabel(name))
        name_row.addStretch(1)
        layout.addLayout(name_row)

        self.btn_capture = CaptureButton()
        self.btn_capture.clicked.connect(self.capture_clicked)
        layout.addWidget(self.btn_capture)

    def set_image(self, image: MatLike | None) -> None:
        self.image.set_image(image)
        self.done_icon.setVisible(image is not None)

    def set_hotkey(self, keys: list[str]) -> None:
        self.btn_capture.set_keys(keys)

    def set_selected(self, selected: bool) -> None:
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


class KeyCap(QWidget):
    """单个按键，显示为强调色圆角块。"""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._text: str = text
        self._font: QFont = getFont(12, QFont.Weight.DemiBold)

    def sizeHint(self) -> QSize:
        text_width = QFontMetrics(self._font).horizontalAdvance(self._text)
        return QSize(max(22, text_width + 12), 22)

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(themeColor())
        painter.drawRoundedRect(QRectF(self.rect()), 4, 4)
        painter.setPen(QColor(0, 0, 0) if isDarkTheme() else QColor(255, 255, 255))
        painter.setFont(self._font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)


class KeyCapRow(QWidget):
    """一组按键，无按键时显示占位文字。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

    def set_keys(self, keys: list[str], placeholder: str | None = None) -> None:
        while self._layout.count():
            widget = self._layout.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        widgets: list[QWidget] = [KeyCap(key) for key in keys]
        if not widgets:
            label = CaptionLabel(placeholder or gt('未设置'))
            label.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))
            widgets.append(label)
        for widget in widgets:
            widget.setFixedSize(widget.sizeHint())
            self._layout.addWidget(widget)

        width = sum(w.width() for w in widgets) + self._layout.spacing() * (len(widgets) - 1)
        self.setFixedSize(width, max(w.height() for w in widgets))


class ShortcutButton(PushButton):
    """显示当前快捷键的按钮。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        PushButton.__init__(self, parent)
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        self.caps = KeyCapRow()
        layout.addWidget(self.caps, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_keys(self, keys: list[str], placeholder: str | None = None) -> None:
        self.caps.set_keys(keys, placeholder)
        self.setFixedWidth(max(88, self.caps.width() + 24))


class AgentCard(CardWidget):
    """列表中的一个代理人，显示快速支援头像、名称和已完成的模板数量。"""

    WIDTH: int = 168

    delete_requested = Signal(str)

    def __init__(self, agent_id: str, avatar: MatLike | None, done_cnt: int, total_cnt: int,
                 parent: QWidget | None = None) -> None:
        CardWidget.__init__(self, parent)
        self.agent_id: str = agent_id
        self.setFixedWidth(self.WIDTH)
        self.setToolTip(agent_id)
        self.installEventFilter(ToolTipFilter(self))
        self.setAccessibleName(agent_id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        avatar_slot = ImageSlot(72, 72)
        avatar_slot.set_image(avatar)
        layout.addWidget(avatar_slot, alignment=Qt.AlignmentFlag.AlignHCenter)

        name_label = BodyLabel()
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setText(QFontMetrics(name_label.font()).elidedText(agent_id, Qt.TextElideMode.ElideRight, self.WIDTH - 24))
        layout.addWidget(name_label)

        state_row = QHBoxLayout()
        state_row.setContentsMargins(0, 0, 0, 0)
        state_row.setSpacing(4)
        state_row.addStretch(1)
        state_icon = IconWidget(FluentIcon.COMPLETED if done_cnt >= total_cnt else InfoBarIcon.WARNING)
        state_icon.setFixedSize(12, 12)
        state_row.addWidget(state_icon)
        state_row.addWidget(CaptionLabel(f'{done_cnt}/{total_cnt}'))
        state_row.addStretch(1)
        layout.addLayout(state_row)

        self.btn_more = TransparentToolButton(FluentIcon.MORE, self)
        self.btn_more.setFixedSize(32, 32)
        self.btn_more.setToolTip(gt('更多'))
        self.btn_more.setAccessibleName(gt('更多'))
        self.btn_more.installEventFilter(ToolTipFilter(self.btn_more))
        self.btn_more.clicked.connect(self._show_menu)
        self.btn_more.move(self.WIDTH - 36, 4)

    def _show_menu(self) -> None:
        menu = RoundMenu(parent=self)
        menu.addAction(Action(FluentIcon.DELETE, gt('删除'), triggered=lambda: self.delete_requested.emit(self.agent_id)))
        menu.exec(self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height())))


class CaptureButton(PushButton):
    """截图按钮，显示相机图标和对应的快捷键。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        PushButton.__init__(self, parent)
        self.setFixedHeight(32)
        self.installEventFilter(ToolTipFilter(self))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)
        layout.addStretch(1)
        icon = IconWidget(FluentIcon.CAMERA)
        icon.setFixedSize(16, 16)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon)
        self.caps = KeyCapRow()
        layout.addWidget(self.caps)
        layout.addStretch(1)

    def set_keys(self, keys: list[str]) -> None:
        self.caps.set_keys(keys)
        text = ' + '.join(keys)
        tip = f'{gt("截图")} ({text})' if text else gt('截图')
        self.setToolTip(tip)
        self.setAccessibleName(tip)
