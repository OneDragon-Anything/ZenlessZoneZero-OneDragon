"""执行态悬浮窗：显示自绘小地图、当前决策与路线进度。

和录制悬浮窗的分工：
- 录制时用 ``BagelRecordOverlay``，要键位说明面板，提示怎么打点。
- 执行时用本文件的 ``BagelRunOverlay``，只关心「现在在哪、在干什么、
  走到第几个点、哪些点已经走过」，所以按键面板整块去掉，
  走过的点画成灰色。

小地图按层底图自绘，不复用小地图截图：截图只有一圈圆形视野，
看不到整条路线，而执行时要判断的是整条路线还剩多少。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import PySide6.QtGui as QtGui
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from pathlib import Path

SCREEN_MARGIN = 24
"""贴屏幕右上角时与屏幕边缘的距离。"""

MAP_SIZE = 200
"""自绘小地图的边长，1:1 取景（层内 200px 对应窗口 200px）。"""

KIND_COLORS: dict[str, QColor] = {
    'beacon': QColor('#7B8CF0'),
    'electronic_safe': QColor('#FFA033'),
    'mechanical_safe': QColor('#C77DFF'),
    'box': QColor('#4ED07A'),
    'door': QColor('#3FC4D8'),
    'elevator': QColor('#F0618F'),
}
"""点位类型到颜色，语义与编辑器网页一致：电子橙、机械紫、普通箱绿。

网页是浅底用深一档，悬浮窗是黑底用亮一档，色相保持相同。
六类色相任意两者至少差 41 度，见网页里的自检。
"""

KIND_LABELS: dict[str, str] = {
    'beacon': '途径点',
    'electronic_safe': '电子箱',
    'mechanical_safe': '机械箱',
    'box': '普通箱',
    'door': '门',
    'elevator': '电梯',
}
"""点位类型到短名，用于决策行里的目标描述。"""

TEXT_COLOR = QColor(232, 232, 232)
DIM_TEXT = QColor(150, 150, 150)
BACKDROP = QColor(0, 0, 0, 190)
MAP_BACKDROP = QColor(28, 28, 30, 235)
MAP_BORDER = QColor(90, 90, 96, 220)
POSITION_COLOR = QColor(255, 90, 90)
EDGE_COLOR = QColor(110, 190, 255, 190)
DONE_EDGE_COLOR = QColor(110, 110, 116, 170)
DONE_POINT_COLOR = QColor(140, 140, 146)
NEXT_POINT_RING = QColor(255, 255, 255, 230)
"""下一个目标点的外圈高亮。"""


class BagelRunOverlay(QWidget):
    """执行期间显示自绘小地图、当前决策与路线进度的悬浮窗。

    所有 setter 都先比较再刷新，避免每帧触发多余重绘。
    """

    PADDING = 8
    LINE_GAP = 2
    MAP_GAP = 6
    WIDTH: int = 250
    TEXT_LINE_COUNT: int = 4

    def __init__(self) -> None:
        """创建无边框置顶窗口，不抢占游戏焦点。"""
        super().__init__(None)
        self.setWindowTitle('贝果路线执行')
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._game_rect: QRect | None = None
        self._lines: list[str] = []
        self._placed: bool = False
        self._drag_offset: QPoint | None = None
        self._font: QFont = QFont('Consolas', 10)
        self._font.setBold(True)
        self.setFixedSize(*self._content_size())

        self._layer_name: str | None = None
        self._layer_pixmap: QPixmap | None = None
        self._points: list[tuple[str, tuple[float, float]]] = []
        self._cursor: int = 0
        self._position: tuple[float, float] | None = None

    def set_game_rect(self, rect: QRect | None) -> None:
        """首次按游戏窗口摆放；之后保持用户拖动后的位置。

        Args:
            rect: 游戏窗口在屏幕上的矩形，None 表示窗口不可用。
        """
        if rect is None or rect.width() <= 0 or rect.height() <= 0:
            self._game_rect = None
            self.hide()
            return
        self._game_rect = rect
        if not self._placed:
            self._move_to_initial_position()
            self._placed = True
        if not self.isVisible():
            self.show()

    def set_lines(self, lines: list[str]) -> None:
        """更新文本行。

        Args:
            lines: 要显示的文本行。
        """
        if lines == self._lines:
            return
        self._lines = list(lines)
        self.setToolTip('\n'.join(lines))
        self.update()

    def set_layer(self, layer_name: str, image_path: Path) -> None:
        """切换底图；同一层重复调用直接忽略。

        Args:
            layer_name: 完整分层名。
            image_path: 该层底图路径。
        """
        if layer_name == self._layer_name and self._layer_pixmap is not None:
            return
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return
        self._layer_name = layer_name
        self._layer_pixmap = pixmap
        self.update()

    def set_route(
        self, points: list[tuple[str, tuple[float, float]]], cursor: int,
    ) -> None:
        """更新路线点位与当前进度。

        Args:
            points: 按顺序排列的（类型, 层内坐标）。
            cursor: 已走到的点下标；小于它的点算走过，画灰色。
        """
        if points == self._points and cursor == self._cursor:
            return
        self._points = points
        self._cursor = cursor
        self.update()

    def set_position(self, local_xy: tuple[float, float] | None) -> None:
        """更新地图上的当前位置。

        Args:
            local_xy: 层内坐标，None 表示这一帧没定位到。
        """
        if local_xy == self._position:
            return
        self._position = local_xy
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """按住任意位置开始拖动窗口。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return
        QWidget.mousePressEvent(self, event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """拖动窗口。"""
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        QWidget.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """结束拖动。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            event.accept()
            return
        QWidget.mouseReleaseEvent(self, event)

    def _move_to_initial_position(self) -> None:
        """贴到游戏所在屏幕的右上角。"""
        screen = self._screen_for_game()
        if screen is None:
            return
        area = screen.availableGeometry()
        width, height = self._content_size()
        self.setGeometry(
            QRect(
                area.right() - SCREEN_MARGIN - width + 1,
                area.top() + SCREEN_MARGIN,
                width,
                height,
            ),
        )

    def _screen_for_game(self) -> QtGui.QScreen | None:
        """取游戏窗口所在的屏幕，找不到时退回主屏。"""
        if self._game_rect is not None:
            screen = QGuiApplication.screenAt(self._game_rect.center())
            if screen is not None:
                return screen
        return QGuiApplication.primaryScreen()

    def _content_size(self) -> tuple[int, int]:
        """固定四行文本区和地图区，尺寸不随决策长度或行数变化。"""
        text_height = self._text_height(QFontMetrics(self._font))
        return self.WIDTH, text_height + self.MAP_GAP + MAP_SIZE + self.PADDING

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制半透明底、文本行与自绘小地图。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self._font)
        painter.fillRect(self.rect(), BACKDROP)

        metrics = painter.fontMetrics()
        text_height = self._text_height(metrics)
        painter.setPen(TEXT_COLOR)
        y = self.PADDING + metrics.ascent()
        text_width = self.width() - self.PADDING * 2
        for line in self._lines[:self.TEXT_LINE_COUNT]:
            visible = metrics.elidedText(line, Qt.TextElideMode.ElideRight, text_width)
            painter.drawText(self.PADDING, y, visible)
            y += metrics.height() + self.LINE_GAP

        self._paint_map(painter, text_height)

    def _text_height(self, metrics: QFontMetrics) -> int:
        """文本区高度，与 _content_size 用同一口径。"""
        line_height = metrics.height() + self.LINE_GAP
        return self.TEXT_LINE_COUNT * line_height + self.PADDING * 2

    def _paint_map(self, painter: QPainter, offset_y: int) -> None:
        """画出取景范围内的层底图、路线、走过点和当前位置。

        取景按整条路线决定，见 ``_map_view``；没定位到位置也能看到整条路线。
        """
        left = self.PADDING
        top = offset_y + self.MAP_GAP
        painter.fillRect(left, top, MAP_SIZE, MAP_SIZE, MAP_BACKDROP)

        view = self._map_view()
        if self._layer_pixmap is None or view is None:
            painter.setPen(QPen(MAP_BORDER, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(left, top, MAP_SIZE, MAP_SIZE)
            return

        center, scale = view
        # 路线可能延伸到裁剪范围之外，必须裁剪，否则线段会画到地图框外面。
        painter.save()
        painter.setClipRect(left, top, MAP_SIZE, MAP_SIZE)
        self._draw_layer(painter, left, top, center, scale)
        self._draw_route(painter, left, top, center, scale)
        self._draw_position(painter, left, top, center, scale)
        painter.restore()

        painter.setPen(QPen(MAP_BORDER, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(left, top, MAP_SIZE, MAP_SIZE)

    def _map_view(self) -> tuple[tuple[float, float], float] | None:
        """算出预览块的取景中心与缩放比例。

        1:1 取景：层内 200px 对应窗口 200px，不缩放。
        中心优先用当前位置，没定位到时用路线中点，
        这样地图上看到的就是角色身边真实大小的一片区域。

        Returns:
            （层内中心坐标, 缩放比例）；没有路线也没位置时返回 None。
        """
        if self._position is not None:
            return self._position, 1.0
        if self._points:
            xs = [point[1][0] for point in self._points]
            ys = [point[1][1] for point in self._points]
            return (sum(xs) / len(xs), sum(ys) / len(ys)), 1.0
        return None

    def _draw_layer(
        self, painter: QPainter, left: int, top: int,
        center: tuple[float, float], scale: float,
    ) -> None:
        """把层底图按取景范围裁一块贴到预览块。"""
        if self._layer_pixmap is None:
            return
        half = MAP_SIZE / 2 / scale
        crop_x = int(center[0] - half)
        crop_y = int(center[1] - half)
        crop_w = int(half * 2)
        crop_h = int(half * 2)
        draw_x, draw_y = left, top
        if crop_x < 0:
            draw_x = int(left - crop_x * scale)
            crop_w += crop_x
            crop_x = 0
        if crop_y < 0:
            draw_y = int(top - crop_y * scale)
            crop_h += crop_y
            crop_y = 0
        crop_w = min(crop_w, self._layer_pixmap.width() - crop_x)
        crop_h = min(crop_h, self._layer_pixmap.height() - crop_y)
        if crop_w <= 0 or crop_h <= 0:
            return
        painter.drawPixmap(
            QRect(draw_x, draw_y, int(crop_w * scale), int(crop_h * scale)),
            self._layer_pixmap,
            QRect(crop_x, crop_y, crop_w, crop_h),
        )

    def _to_screen(
        self, point: tuple[float, float], left: int, top: int,
        center: tuple[float, float], scale: float,
    ) -> tuple[float, float]:
        """层内坐标换算成预览块内坐标。"""
        half = MAP_SIZE / 2 / scale
        return (
            left + (point[0] - (center[0] - half)) * scale,
            top + (point[1] - (center[1] - half)) * scale,
        )

    def _draw_route(
        self, painter: QPainter, left: int, top: int,
        center: tuple[float, float], scale: float,
    ) -> None:
        """画路线连线与点位；走过的一段用灰色，未走的用蓝色。"""
        for index in range(1, len(self._points)):
            start = self._to_screen(
                self._points[index - 1][1], left, top, center, scale,
            )
            end = self._to_screen(self._points[index][1], left, top, center, scale)
            done = index <= self._cursor
            painter.setPen(QPen(DONE_EDGE_COLOR if done else EDGE_COLOR, 2))
            painter.drawLine(QPointF(*start), QPointF(*end))

        for index, (kind, point) in enumerate(self._points):
            x, y = self._to_screen(point, left, top, center, scale)
            done = index < self._cursor
            color = DONE_POINT_COLOR if done else KIND_COLORS.get(kind, POSITION_COLOR)
            if index == self._cursor:
                painter.setPen(QPen(NEXT_POINT_RING, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(x, y), 7, 7)
            painter.setPen(QPen(color, 2))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), 4, 4)

    def _draw_position(
        self, painter: QPainter, left: int, top: int,
        center: tuple[float, float], scale: float,
    ) -> None:
        """当前位置画成红圈。"""
        if self._position is None:
            return
        x, y = self._to_screen(self._position, left, top, center, scale)
        painter.setPen(QPen(POSITION_COLOR, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(x, y), 5, 5)
