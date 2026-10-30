from PySide6.QtGui import QMouseEvent
from qfluentwidgets import ListWidget


class MultiSelectListWidget(ListWidget):
    """修复 qfluentwidgets ListWidget 在 MultiSelection 模式下取消选中后残留高亮

    根因：TableItemDelegate.setSelectedRows 中，取消选中的行的 pressedRow
    未被清除，导致 paint 方法仍为该行绘制 pressed 背景。
    """

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        super().mouseReleaseEvent(e)
        self.delegate.setPressedRow(-1)
        self.viewport().update()
