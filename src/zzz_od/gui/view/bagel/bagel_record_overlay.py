"""录制时显示的悬浮窗：定位文本、朝向罗盘、层底图局部预览与已打点位。

自绘窗口，只依赖 Qt，不引用插件代码。窗口置顶、无边框、可拖动，
默认贴在屏幕右上角，之后用户拖到哪就留在哪。
"""

from __future__ import annotations

import math
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

MAP_PREVIEW_SIZE = 200
"""层底图局部预览的边长，与插件一致。"""

MARKER_PANEL_WIDTH = 128
"""预览右侧键位说明面板的宽度。"""

MARKER_ROW_HEIGHT = 23
"""键位说明每行的高度。"""

MARKER_COLORS: dict[str, QColor] = {
    'beacon': QColor('#FFDC46'),
    'electronic_safe': QColor('#50D2FF'),
    'mechanical_safe': QColor('#FF9646'),
    'box': QColor('#D282FF'),
    'door': QColor('#64F096'),
    'elevator': QColor('#FF64A0'),
    'delete': QColor('#B0B0B0'),
}
"""点位类型到显示颜色，与插件保持一致。"""

MARKER_ITEMS: tuple[tuple[str, str, str], ...] = (
    ('1', '途径点', 'beacon'),
    ('2', '电子保险箱', 'electronic_safe'),
    ('3', '机械保险箱', 'mechanical_safe'),
    ('4', '普通箱子', 'box'),
    ('5', '门', 'door'),
    ('6', '电梯', 'elevator'),
    ('退格', '删上一个点', 'delete'),
)
"""键位说明面板的条目：(按键, 名称, 类型)。"""

SECTOR_COLOR = QColor(90, 200, 255)
MARKER_COLOR = QColor(255, 205, 90)
TEXT_COLOR = QColor(232, 232, 232)
BACKDROP = QColor(0, 0, 0, 178)
MAP_BACKDROP = QColor(35, 35, 35, 220)
MAP_EMPTY_BORDER = QColor(80, 80, 80, 200)
RECORDING_COLOR = QColor(255, 96, 96)
IDLE_COLOR = QColor(140, 140, 140)
POSITION_COLOR = QColor(255, 90, 90)
POINT_COLOR = QColor(120, 220, 255)
EDGE_COLOR = QColor(120, 220, 255, 210)
"""预览里点位之间的连线颜色，与插件一致。"""


class BagelRecordOverlay(QWidget):
    """录制期间显示实时状态的可拖动悬浮窗。

    所有 setter 都先比较再刷新，避免每帧触发多余重绘。
    """

    PADDING = 8
    MIN_WIDTH = 260
    COMPASS_SIZE = 64
    COMPASS_GAP = 10
    MAP_GAP = 6
    LINE_GAP = 2

    def __init__(self) -> None:
        """创建无边框置顶窗口，默认不抢占游戏焦点。"""
        super().__init__(None)
        self.setWindowTitle('贝果路线录制')
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
        self._sector_angle: float | None = None
        self._marker_angle: float | None = None
        self._recording: bool = False
        self._placed: bool = False
        self._drag_offset: QPoint | None = None
        self._font: QFont = QFont('Consolas', 10)
        self._font.setBold(True)

        self._layer_name: str | None = None
        self._layer_pixmap: QPixmap | None = None
        self._local_position: tuple[float, float] | None = None
        self._points: list[tuple[str, tuple[float, float]]] = []
        self._marker_font: QFont = QFont('Microsoft YaHei UI', 9)

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
            lines: 逐行显示的文本。
        """
        if lines == self._lines:
            return
        self._lines = list(lines)
        self._resize_preserving_position()
        self.update()

    def set_angles(self, sector: float | None, marker: float | None) -> None:
        """更新镜头与角色朝向箭头。

        Args:
            sector: 镜头朝向角度。
            marker: 角色朝向角度。
        """
        if sector == self._sector_angle and marker == self._marker_angle:
            return
        self._sector_angle = sector
        self._marker_angle = marker
        self.update()

    @property
    def sector_angle(self) -> float | None:
        """当前镜头朝向角度，供文本行显示。"""
        return self._sector_angle

    @property
    def marker_angle(self) -> float | None:
        """当前角色朝向角度，供文本行显示。"""
        return self._marker_angle

    def set_recording(self, recording: bool) -> None:
        """更新录制状态，用于罗盘中心的红点。

        Args:
            recording: 是否正在录制。
        """
        if recording == self._recording:
            return
        self._recording = recording
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
        self._points = []
        self._resize_preserving_position()
        self.update()

    def set_position(self, local_xy: tuple[float, float] | None) -> None:
        """更新预览里的当前位置，坐标用层内坐标。

        Args:
            local_xy: 层内坐标，None 表示这一帧没定位到。
        """
        if local_xy == self._local_position:
            return
        self._local_position = local_xy
        self.update()

    def add_point(self, local_xy: tuple[float, float], kind: str = 'beacon') -> None:
        """记录一个已打下的点位，在预览里按类型着色画成小圆点。

        Args:
            local_xy: 层内坐标。
            kind: 点位类型标识。
        """
        self._points.append((kind, local_xy))
        self.update()

    def clear_points(self) -> None:
        """清空已打点位。"""
        if not self._points:
            return
        self._points = []
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

    def _resize_preserving_position(self) -> None:
        """内容变化后调整尺寸；右边界保持不动，贴角时不跑位。"""
        if not self._placed:
            return
        right = self.x() + self.width()
        width, height = self._content_size()
        self.resize(width, height)
        self.move(right - width, self.y())

    def _text_size(self) -> tuple[int, int]:
        """按最长一行算文本区域。"""
        metrics = QFontMetrics(self._font)
        line_height = metrics.height() + self.LINE_GAP
        if not self._lines:
            return self.MIN_WIDTH, line_height + self.PADDING * 2
        width = max(
            self.MIN_WIDTH,
            max(metrics.horizontalAdvance(line) for line in self._lines)
            + self.PADDING * 2,
        )
        return width, len(self._lines) * line_height + self.PADDING * 2

    def _content_size(self) -> tuple[int, int]:
        """文本与罗盘并排，下面接底图预览和右侧键位面板。"""
        text_width, text_height = self._text_size()
        top_width = text_width + self.COMPASS_GAP + self.COMPASS_SIZE + self.PADDING
        map_width = MAP_PREVIEW_SIZE + MARKER_PANEL_WIDTH + self.PADDING * 3
        width = max(top_width, map_width)
        top_height = max(text_height, self.COMPASS_SIZE + self.PADDING * 2)
        return width, top_height + self.MAP_GAP + MAP_PREVIEW_SIZE + self.PADDING

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制半透明底、文本行、朝向罗盘、底图预览与键位说明。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self._font)
        width, height = self._content_size()
        painter.fillRect(0, 0, width, height, BACKDROP)

        metrics = painter.fontMetrics()
        text_width, text_height = self._text_size()
        painter.setPen(TEXT_COLOR)
        y = self.PADDING + metrics.ascent()
        for line in self._lines:
            painter.drawText(self.PADDING, y, line)
            y += metrics.height() + self.LINE_GAP

        self._paint_compass(
            painter,
            center_x=text_width + self.COMPASS_GAP + self.COMPASS_SIZE // 2,
            center_y=text_height // 2,
        )
        self._paint_map(painter, text_height)
        self._paint_marker_panel(painter, text_height)

    def _paint_compass(self, painter: QPainter, center_x: int, center_y: int) -> None:
        """绘制罗盘底圈、四个刻度与两支朝向箭头。"""
        radius = self.COMPASS_SIZE // 2 - 2
        center = QPointF(center_x, center_y)
        painter.setPen(QPen(IDLE_COLOR, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)
        for angle in (0, 90, 180, 270):
            rad = math.radians(angle)
            inner = radius - 5
            painter.drawLine(
                QPointF(center_x + inner * math.cos(rad), center_y - inner * math.sin(rad)),
                QPointF(center_x + radius * math.cos(rad), center_y - radius * math.sin(rad)),
            )
        for angle, color in (
            (self._sector_angle, SECTOR_COLOR),
            (self._marker_angle, MARKER_COLOR),
        ):
            if angle is not None:
                self._paint_arrow(painter, center, radius, angle, color)
        if self._recording:
            painter.setPen(QPen(RECORDING_COLOR, 2))
            painter.setBrush(RECORDING_COLOR)
            painter.drawEllipse(QPointF(center_x, center_y), 3, 3)

    def _paint_map(self, painter: QPainter, offset_y: int) -> None:
        """以当前位置为中心裁一块层底图，并画出位置点、朝向与已打点位。

        预览块贴左边距摆放，右侧留给键位说明面板。
        """
        left = self.PADDING
        top = offset_y + self.MAP_GAP
        half = MAP_PREVIEW_SIZE // 2
        painter.fillRect(left, top, MAP_PREVIEW_SIZE, MAP_PREVIEW_SIZE, MAP_BACKDROP)
        if self._layer_pixmap is None or self._local_position is None:
            painter.setPen(QPen(MAP_EMPTY_BORDER, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(left, top, MAP_PREVIEW_SIZE, MAP_PREVIEW_SIZE)
            return

        center_x = self._local_position[0]
        center_y = self._local_position[1]
        crop_x = center_x - half
        crop_y = center_y - half
        draw_x, draw_y = left, top
        crop_w, crop_h = MAP_PREVIEW_SIZE, MAP_PREVIEW_SIZE
        if crop_x < 0:
            draw_x = left - crop_x
            crop_w += crop_x
            crop_x = 0
        if crop_y < 0:
            draw_y = top - crop_y
            crop_h += crop_y
            crop_y = 0
        crop_w = min(crop_w, self._layer_pixmap.width() - crop_x)
        crop_h = min(crop_h, self._layer_pixmap.height() - crop_y)
        if crop_w <= 0 or crop_h <= 0:
            return
        painter.drawPixmap(
            QRect(int(draw_x), int(draw_y), int(crop_w), int(crop_h)),
            self._layer_pixmap,
            QRect(int(crop_x), int(crop_y), int(crop_w), int(crop_h)),
        )

        for index in range(1, len(self._points)):
            prev = self._points[index - 1]
            cur = self._points[index]
            start_x = left + prev[1][0] - (center_x - half)
            start_y = top + prev[1][1] - (center_y - half)
            end_x = left + cur[1][0] - (center_x - half)
            end_y = top + cur[1][1] - (center_y - half)
            painter.setPen(QPen(EDGE_COLOR, 2))
            painter.drawLine(QPointF(start_x, start_y), QPointF(end_x, end_y))

        if self._points:
            last = self._points[-1]
            painter.setPen(QPen(EDGE_COLOR, 2))
            painter.drawLine(
                QPointF(
                    left + last[1][0] - (center_x - half),
                    top + last[1][1] - (center_y - half),
                ),
                QPointF(left + half, top + half),
            )

        for kind, point in self._points:
            point_x = left + point[0] - (center_x - half)
            point_y = top + point[1] - (center_y - half)
            if not (left <= point_x < left + MAP_PREVIEW_SIZE):
                continue
            if not (top <= point_y < top + MAP_PREVIEW_SIZE):
                continue
            color = MARKER_COLORS.get(kind, POINT_COLOR)
            painter.setPen(QPen(color, 2))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(point_x, point_y), 4, 4)

        dot_x = left + half
        dot_y = top + half
        painter.setPen(QPen(POSITION_COLOR, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(dot_x, dot_y), 4, 4)
        angle = self._marker_angle if self._marker_angle is not None else self._sector_angle
        if angle is not None:
            rad = math.radians(angle)
            painter.drawLine(
                QPointF(dot_x, dot_y),
                QPointF(dot_x + 22 * math.cos(rad), dot_y - 22 * math.sin(rad)),
            )

    def _paint_marker_panel(self, painter: QPainter, offset_y: int) -> None:
        """在预览右侧画键位说明：类型色点、按键、名称。

        按键文字有「1」也有「退格」，名称的起始位置按按键实际宽度往后挪，
        否则两个字宽的按键会和名称叠在一起。
        """
        left = self.PADDING * 2 + MAP_PREVIEW_SIZE
        top = offset_y + self.MAP_GAP
        painter.setFont(self._marker_font)
        metrics = QFontMetrics(self._marker_font)
        key_left = left + 17
        for index, (key, name, marker_type) in enumerate(MARKER_ITEMS):
            y = top + index * MARKER_ROW_HEIGHT
            color = MARKER_COLORS[marker_type]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(left, y + 5, 10, 10)
            painter.setPen(TEXT_COLOR)
            painter.drawText(key_left, y + 5 + metrics.ascent(), key)
            painter.setPen(color)
            painter.drawText(
                key_left + max(20, metrics.horizontalAdvance(key) + 6),
                y + 5 + metrics.ascent(),
                name,
            )

    @staticmethod
    def _paint_arrow(
        painter: QPainter, center: QPointF, radius: int, angle: float, color: QColor,
    ) -> None:
        """从圆心朝角度画一支带箭头的线；角度按正右为 0、逆时针增加。"""
        rad = math.radians(angle)
        tip = QPointF(
            center.x() + radius * math.cos(rad),
            center.y() - radius * math.sin(rad),
        )
        painter.setPen(QPen(color, 2))
        painter.drawLine(center, tip)
        for sign in (1, -1):
            wing_rad = rad + sign * math.radians(150)
            painter.drawLine(
                tip,
                QPointF(
                    tip.x() + 7 * math.cos(wing_rad),
                    tip.y() - 7 * math.sin(wing_rad),
                ),
            )
