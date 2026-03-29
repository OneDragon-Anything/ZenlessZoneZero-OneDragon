from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication, QHBoxLayout, QScrollArea
from qfluentwidgets import TeachingTip as qtTeachingTip
from qfluentwidgets import TeachingTipTailPosition, isDarkTheme
from qfluentwidgets.components.widgets.teaching_tip import (
    TeachingTipManager,
    TeachTipBubble,
)


class ThemedBubble(TeachTipBubble):
    """paintEvent 匹配项目主题色的 TeachTipBubble。"""

    def paintEvent(self, e) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        if isDarkTheme():
            painter.setBrush(QColor(35, 39, 46))
            painter.setPen(QColor(78, 78, 78))
        else:
            painter.setBrush(QColor(248, 248, 248))
            painter.setPen(QColor(0, 0, 0, 17))
        self.manager.draw(self, painter)


class TeachingTip(qtTeachingTip):
    """增强版 TeachingTip：

    1. 点击三角形 / 透明 margin 区域关闭
    2. 点击外部区域关闭（通过 QApplication 事件过滤器检测）
    3. Alt+Tab 切换窗口时跟随父窗口隐藏（Qt.Tool 特性）
    4. 气泡背景色匹配项目主题（替代 qfluentwidgets 硬编码的 #282828）
    """

    def __init__(self, view, target, duration=1000,
                 tailPosition=TeachingTipTailPosition.BOTTOM, parent=None, isDeleteOnClose=True):
        # 跳过 qtTeachingTip.__init__，用 ThemedBubble 替代 TeachTipBubble
        super(qtTeachingTip, self).__init__(parent=parent)
        self.target = target
        self.duration = duration
        self.isDeleteOnClose = isDeleteOnClose
        self.manager = TeachingTipManager.make(tailPosition)

        self.hBoxLayout = QHBoxLayout(self)
        self.opacityAni = QPropertyAnimation(self, b'windowOpacity', self)

        self.bubble = ThemedBubble(view, tailPosition, self)

        self.hBoxLayout.setContentsMargins(15, 8, 15, 20)
        self.hBoxLayout.addWidget(self.bubble)
        self.setShadowEffect()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)

        if parent and parent.window():
            parent.window().installEventFilter(self)

    def _view_rect_in_tip(self) -> QRect:
        """将 view（内容区域）的矩形映射到 tip 坐标系。"""
        view = self.view
        top_left = view.mapTo(self, view.rect().topLeft())
        return QRect(top_left, view.rect().size())

    def _bubble_global_rect(self) -> QRect:
        """将 bubble（气泡内容区域）的矩形映射到全局坐标系。"""
        bubble = self.bubble
        top_left = bubble.mapToGlobal(bubble.rect().topLeft())
        return QRect(top_left, bubble.rect().size())

    def showEvent(self, e) -> None:
        super().showEvent(e)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._target_global_pos = self.target.mapToGlobal(QPoint(0, 0))

    def _follow_target(self) -> None:
        """target 位置改变时跟随移动；滚出可视区域时关闭。"""
        try:
            if not self._target_visible():
                self.close()
                return
            current = self.target.mapToGlobal(QPoint(0, 0))
            if current != self._target_global_pos:
                delta = current - self._target_global_pos
                self.move(self.pos() + delta)
                self._target_global_pos = current
        except RuntimeError:
            self.close()

    def _target_visible(self) -> bool:
        """检查 target 是否在其父 QScrollArea 的可视区域内。"""
        parent = self.target.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                viewport = parent.viewport()
                target_rect = self.target.rect()
                # target 矩形映射到 viewport 坐标系
                mapped_tl = self.target.mapTo(viewport, target_rect.topLeft())
                mapped_br = self.target.mapTo(viewport, target_rect.bottomRight())
                mapped_rect = QRect(mapped_tl, mapped_br)
                return viewport.rect().intersects(mapped_rect)
            parent = parent.parentWidget()
        return True

    def resizeEvent(self, event) -> None:
        """宽度变化时用实际宽度重新定位，修正 sizeHint != width 导致的偏移。"""
        super().resizeEvent(event)
        if not self.isVisible() or not hasattr(self, 'target'):
            return
        target_left = self.target.mapToGlobal(self.target.rect().topLeft()).x()
        m = self.layout().contentsMargins()
        desired_x = target_left - self.width() + m.right()
        if self.x() != desired_x:
            self.move(desired_x, self.y())

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

    def eventFilter(self, obj, e: QEvent):
        if e.type() == QEvent.Type.MouseButtonPress and isinstance(e, QMouseEvent):
            # ComboBox 下拉等弹出控件打开时跳过关闭
            if QApplication.activePopupWidget() is not None:
                return super().eventFilter(obj, e)
            global_pos = e.globalPosition().toPoint()
            if not self._bubble_global_rect().contains(global_pos):
                self.close()
        elif e.type() == QEvent.Type.Wheel:
            # Wheel 在 scroll area 处理之前触发，延到下一帧读取新位置
            QTimer.singleShot(0, self._follow_target)
        return super().eventFilter(obj, e)
