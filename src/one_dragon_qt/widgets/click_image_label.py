from enum import Enum

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ImageLabel

from one_dragon.base.config.config_item import ConfigItem


class ImageScaleEnum(Enum):

    SCALE_100 = ConfigItem(label='原图', value=1)
    SCALE_50 = ConfigItem(label='0.5x', value=0.5)
    X2 = ConfigItem(label='2x', value=2.0)
    X4 = ConfigItem(label='4x', value=4.0)
    X8 = ConfigItem(label='8x', value=8.0)

class ClickImageLabel(ImageLabel):

    clicked_with_pos = Signal(int, int)
    right_clicked_with_pos = Signal(int, int)  # 新增右键点击信号
    drag_released = Signal(int, int, int, int)

    def __init__(self, parent: QWidget = None):
        ImageLabel.__init__(self, parent)

        self._press_pos: QPoint = None
        self._release_pos: QPoint = None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
            self.clicked_with_pos.emit(self._press_pos.x(), self._press_pos.y())
        elif event.button() == Qt.MouseButton.RightButton:
            pos = event.pos()
            self.right_clicked_with_pos.emit(pos.x(), pos.y())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._release_pos = event.pos()
            if self._press_pos is not None:
                self.drag_released.emit(self._press_pos.x(), self._press_pos.y(),
                                        self._release_pos.x(), self._release_pos.y())
