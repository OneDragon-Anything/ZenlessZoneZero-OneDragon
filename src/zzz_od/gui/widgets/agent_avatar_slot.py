from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QFrame
from qfluentwidgets import isDarkTheme

from one_dragon.base.screen.template_info import get_template_raw_path
from zzz_od.game_data.agent import Agent, AgentEnum

UNKNOWN_AGENT_ID = "unknown"
UNKNOWN_AGENT_NAME = "未选择"
PLACEHOLDER_TEXT = "选择代理人"

_AGENT_PIXMAP_CACHE: dict[str, QPixmap] = {}


def build_yahei_font(point_size: int, weight: int = QFont.Weight.Medium) -> QFont:
    font = QFont("Microsoft YaHei UI", point_size)
    font.setWeight(weight)
    return font


@lru_cache(maxsize=1)
def get_agent_map() -> dict[str, Agent]:
    return {agent.value.agent_id: agent.value for agent in AgentEnum}


@lru_cache(maxsize=2)
def get_all_agent_options(include_unknown: bool = True) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    if include_unknown:
        options.append((UNKNOWN_AGENT_ID, UNKNOWN_AGENT_NAME))
    options.extend((agent.value.agent_id, agent.value.agent_name) for agent in AgentEnum)
    return options


def normalize_agent_id(agent_id: str | None) -> str:
    if agent_id in get_agent_map():
        return agent_id
    return UNKNOWN_AGENT_ID


def get_agent_display_name(agent_id: str | None) -> str:
    normalized_agent_id = normalize_agent_id(agent_id)
    if normalized_agent_id == UNKNOWN_AGENT_ID:
        return UNKNOWN_AGENT_NAME
    return get_agent_map()[normalized_agent_id].agent_name


def get_agent_avatar_path(agent_id: str | None) -> str | None:
    normalized_agent_id = normalize_agent_id(agent_id)
    if normalized_agent_id == UNKNOWN_AGENT_ID:
        return None

    avatar_path = get_template_raw_path(
        "predefined_team", f"avatar_{normalized_agent_id}"
    )
    return avatar_path if Path(avatar_path).exists() else None


def get_agent_avatar_pixmap(agent_id: str | None) -> QPixmap | None:
    normalized_agent_id = normalize_agent_id(agent_id)
    if normalized_agent_id == UNKNOWN_AGENT_ID:
        return None

    if normalized_agent_id not in _AGENT_PIXMAP_CACHE:
        avatar_path = get_agent_avatar_path(normalized_agent_id)
        _AGENT_PIXMAP_CACHE[normalized_agent_id] = (
            QPixmap(avatar_path) if avatar_path is not None else QPixmap()
        )

    pixmap = _AGENT_PIXMAP_CACHE[normalized_agent_id]
    return None if pixmap.isNull() else pixmap


def draw_cover_pixmap(
    painter: QPainter, rect: QRect, pixmap: QPixmap | None, radius: float = 0
) -> None:
    if pixmap is None or pixmap.isNull() or rect.width() <= 0 or rect.height() <= 0:
        return

    scaled_pixmap = get_cover_scaled_pixmap(pixmap, rect.size())
    if scaled_pixmap is None:
        return

    painter.save()
    if radius > 0:
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(clip_path)
    painter.drawPixmap(rect.topLeft(), scaled_pixmap)
    painter.restore()


def get_cover_scaled_pixmap(pixmap: QPixmap | None, target_size: QSize) -> QPixmap | None:
    if (
        pixmap is None
        or pixmap.isNull()
        or target_size.width() <= 0
        or target_size.height() <= 0
    ):
        return None

    scaled = pixmap.scaled(
        target_size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    if scaled.isNull():
        return None

    x = max(0, (scaled.width() - target_size.width()) // 2)
    y = max(0, (scaled.height() - target_size.height()) // 2)
    return scaled.copy(x, y, target_size.width(), target_size.height())


class AgentAvatarSlot(QFrame):

    agent_changed = Signal(str)

    SKEW_OFFSET = 12
    NAME_BAR_HEIGHT = 18
    BADGE_WIDTH = 24
    BADGE_HEIGHT = 14

    def __init__(self, slot_index: int, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self._agent_id = UNKNOWN_AGENT_ID
        self._hovered = False
        self._popup_active = False

        self.setObjectName("agentAvatarSlot")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(110, 50)
        self.setMouseTracking(True)
        self._refresh_tooltip()

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def set_agent_id(self, agent_id: str | None) -> None:
        self._agent_id = normalize_agent_id(agent_id)
        self._refresh_tooltip()
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.pos())
        ):
            self._show_picker()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        card_rect = self.rect().adjusted(1, 1, -1, -1)
        card_path = self._create_parallelogram_path(card_rect)
        image_rect = QRect(card_rect)
        name_rect = QRect(
            card_rect.left(),
            card_rect.bottom() - self.NAME_BAR_HEIGHT + 1,
            card_rect.width(),
            self.NAME_BAR_HEIGHT,
        )
        accent_rect = QRect(
            card_rect.left() + 2,
            card_rect.bottom() - 3,
            card_rect.width() - 4,
            3,
        )

        is_dark = isDarkTheme()
        base_color = QColor(25, 27, 33) if is_dark else QColor(234, 238, 244)
        placeholder_color = QColor(212, 216, 224) if is_dark else QColor(92, 101, 116)
        name_text_color = QColor(247, 249, 252) if is_dark else QColor(255, 255, 255)
        badge_bg = QColor(6, 8, 12, 150) if is_dark else QColor(12, 16, 22, 126)
        border_color = QColor(82, 88, 100, 190) if is_dark else QColor(168, 176, 190, 215)
        hover_border_color = QColor(114, 168, 245, 210) if is_dark else QColor(120, 142, 188, 215)
        accent_color = QColor(50, 154, 255) if is_dark else QColor(58, 125, 240)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base_color)
        painter.drawPath(card_path)

        pixmap = get_agent_avatar_pixmap(self._agent_id)
        if pixmap is not None:
            scaled_pixmap = get_cover_scaled_pixmap(pixmap, image_rect.size())
            if scaled_pixmap is not None:
                painter.save()
                painter.setClipPath(card_path)
                painter.drawPixmap(image_rect.topLeft(), scaled_pixmap)
                painter.restore()
        else:
            painter.fillPath(card_path, QColor(42, 45, 54) if is_dark else QColor(236, 240, 246))
            painter.setPen(placeholder_color)
            painter.setFont(build_yahei_font(8, QFont.Weight.Medium))
            painter.drawText(
                image_rect.adjusted(0, -10, 0, -self.NAME_BAR_HEIGHT),
                Qt.AlignmentFlag.AlignCenter,
                PLACEHOLDER_TEXT,
            )

        painter.save()
        painter.setClipPath(card_path)
        gradient = QLinearGradient(
            QPointF(name_rect.left(), name_rect.top()),
            QPointF(name_rect.left(), name_rect.bottom()),
        )
        if is_dark:
            gradient.setColorAt(0.0, QColor(4, 6, 10, 12))
            gradient.setColorAt(1.0, QColor(4, 6, 10, 214))
        else:
            gradient.setColorAt(0.0, QColor(12, 14, 18, 18))
            gradient.setColorAt(1.0, QColor(12, 14, 18, 196))
        painter.fillRect(name_rect, gradient)
        painter.restore()

        badge_rect = QRect(
            card_rect.right() - self.BADGE_WIDTH - 6,
            card_rect.top() + 4,
            self.BADGE_WIDTH,
            self.BADGE_HEIGHT,
        )
        painter.setBrush(badge_bg)
        painter.drawRoundedRect(badge_rect, 7, 7)
        painter.setPen(QColor(245, 247, 250))
        painter.setFont(build_yahei_font(7, QFont.Weight.DemiBold))
        painter.drawText(
            badge_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{self.slot_index}P",
        )

        agent_name = get_agent_display_name(self._agent_id)
        painter.setFont(build_yahei_font(8, QFont.Weight.Medium))
        elided_name = painter.fontMetrics().elidedText(
            agent_name,
            Qt.TextElideMode.ElideRight,
            name_rect.width() - 10,
        )
        painter.setPen(name_text_color)
        painter.drawText(
            name_rect.adjusted(5, 0, -5, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            elided_name,
        )

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(hover_border_color if self._hovered else border_color, 1.25))
        painter.drawPath(card_path)

        if self._popup_active:
            painter.save()
            painter.setClipPath(card_path)
            painter.fillRect(accent_rect, accent_color)
            painter.restore()

    def _show_picker(self) -> None:
        from zzz_od.gui.widgets.agent_picker_popup import AgentPickerPopup

        self._popup_active = True
        self.update()

        tip = AgentPickerPopup.show_popup(
            target=self,
            current_agent_id=self._agent_id,
            on_agent_selected=self._on_agent_selected,
            parent=self.window(),
        )
        if tip is not None:
            tip.destroyed.connect(self._on_popup_closed)
        else:
            self._on_popup_closed()

    def _on_agent_selected(self, agent_id: str) -> None:
        normalized_agent_id = normalize_agent_id(agent_id)
        if normalized_agent_id == self._agent_id:
            return

        self._agent_id = normalized_agent_id
        self._refresh_tooltip()
        self.update()
        self.agent_changed.emit(normalized_agent_id)

    def _on_popup_closed(self) -> None:
        self._popup_active = False
        self.update()

    def _refresh_tooltip(self) -> None:
        self.setToolTip(get_agent_display_name(self._agent_id))

    def _create_parallelogram_path(self, rect: QRect) -> QPainterPath:
        skew = min(self.SKEW_OFFSET, max(10, rect.height() // 4))
        path = QPainterPath()
        path.moveTo(QPointF(rect.left() + skew, rect.top()))
        path.lineTo(QPointF(rect.right(), rect.top()))
        path.lineTo(QPointF(rect.right() - skew, rect.bottom()))
        path.lineTo(QPointF(rect.left(), rect.bottom()))
        path.closeSubpath()
        return path
