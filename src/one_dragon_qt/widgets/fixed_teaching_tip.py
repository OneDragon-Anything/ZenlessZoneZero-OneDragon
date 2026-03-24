from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from qfluentwidgets import TeachingTip


class FixedTeachingTip(TeachingTip):
    """修复 TeachingTip：

    1. 点击三角形 / 透明 margin 区域关闭
    2. 点击外部区域关闭（通过 QApplication 事件过滤器检测）
    3. Alt+Tab 切换窗口时跟随父窗口隐藏（Qt.Tool 特性）
    4. 禁用系统原生阴影，避免与 QGraphicsDropShadowEffect 叠加
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.NoDropShadowWindowHint
        )

    def _view_rect_in_tip(self) -> QRect:
        """将 view（内容区域）的矩形映射到 tip 坐标系。"""
        view = self.view
        top_left = view.mapTo(self, view.rect().topLeft())
        return QRect(top_left, view.rect().size())

    def showEvent(self, e) -> None:
        super().showEvent(e)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def closeEvent(self, e) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().closeEvent(e)

    def mousePressEvent(self, event) -> None:
        if not self._view_rect_in_tip().contains(event.position().toPoint()):
            self.close()
            return
        super().mousePressEvent(event)

    def eventFilter(self, obj, event: QEvent):  # type: ignore[override]
        if event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            # ComboBox 等下拉菜单打开时不关闭 tip
            if QApplication.activePopupWidget() is not None:
                return super().eventFilter(obj, event)
            global_pos = event.globalPosition().toPoint()
            if not self.geometry().contains(global_pos):
                self.close()
        return super().eventFilter(obj, event)
