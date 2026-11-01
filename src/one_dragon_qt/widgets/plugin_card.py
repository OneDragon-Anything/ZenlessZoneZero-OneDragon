"""插件市场的卡片与卡片网格。

卡片整块就是封面：封面由插件标识生成配色，底部渐变压住名称与版本信息，
左上角的实心标签表示订阅或安装状态。点击卡片弹出插件详情。
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPixmap,
    QRadialGradient,
    QResizeEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FlowLayout,
    FluentIcon,
    ImageLabel,
    StrongBodyLabel,
    TransparentToolButton,
    setCustomStyleSheet,
)

CARD_WIDTH = 300
CARD_HEIGHT = 188
CORNER_RADIUS = 10

BADGE_SUBSCRIBED = 'subscribed'
BADGE_INSTALLED = 'installed'
BADGE_UPDATE = 'update'
BADGE_NONE = 'none'

BADGE_COLORS: dict[str, tuple[str, str]] = {
    BADGE_SUBSCRIBED: ('#0f6cbd', '#2b88d8'),
    BADGE_INSTALLED: ('#0b6a4a', '#138a5e'),
    BADGE_UPDATE: ('#b85c00', '#c96a12'),
    BADGE_NONE: ('#5d5d5d', '#6b6b6b'),
}
"""标签实心底色：浅色主题、深色主题。文字统一用白色。"""


def cover_colors(seed: str) -> tuple[QColor, QColor]:
    """按插件标识生成一对封面配色，同一个插件每次都是同一个颜色。"""
    digest = hashlib.sha256((seed or '').encode('utf-8')).digest()
    hue = digest[0] * 360 // 256
    accent_hue = (hue + 40 + digest[1] * 40 // 256) % 360
    return (
        QColor.fromHsl(hue, 165, 52),
        QColor.fromHsl(accent_hue, 200, 24),
    )


class _CardOverlay(QWidget):
    """卡片封面之上的遮罩：底部渐变压住文字、悬停高亮与描边。

    封面交给组件库的 ImageLabel 绘制，父控件的 paintEvent 会被它盖住，
    所以这些覆盖层单独放一个透明控件，叠在封面之上、文字之下。
    封面本身的明暗由插件发布者决定，这里不再整卡压暗。
    """

    def __init__(self, parent: QWidget) -> None:
        """初始化遮罩层。

        Args:
            parent: 遮罩所属的卡片控件，遮罩始终与卡片等大并叠在封面之上。
        """
        super().__init__(parent)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._hover: bool = False

    def set_hover(self, hover: bool) -> None:
        """同步悬停状态。"""
        if self._hover == hover:
            return
        self._hover = hover
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制封面之上的覆盖层。

        先按圆角裁切，再画底部由透明到深色的渐变，让压在上面的白色文字
        在浅色封面上也能看清；悬停时叠一层白色高亮，最后描一圈圆角边框。

        Args:
            event: Qt 绘制事件，本方法按控件自身尺寸重绘，不读取事件内容。
        """
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)
        painter.setClipPath(path)

        shade = QLinearGradient(QPointF(0, rect.height() * 0.38), QPointF(0, rect.height()))
        shade.setColorAt(0.0, QColor(0, 0, 0, 0))
        shade.setColorAt(1.0, QColor(0, 0, 0, 200))
        painter.fillRect(rect, shade)

        if self._hover and self.isEnabled():
            painter.fillRect(rect, QColor(255, 255, 255, 14))

        painter.setClipping(False)
        border_alpha = 90 if self._hover and self.isEnabled() else 28
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor(255, 255, 255, border_alpha))
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, rect.width() - 1, rect.height() - 1),
            CORNER_RADIUS,
            CORNER_RADIUS,
        )
        painter.end()


class PluginCard(QWidget):
    """一个插件的卡片，整块是封面。"""

    clicked = Signal()

    def __init__(
        self,
        title: str,
        meta_text: str,
        seed: str = '',
        badge_text: str = '',
        badge_kind: str = BADGE_NONE,
        cover: QPixmap | None = None,
        on_click: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_click: Callable[[], None] | None = on_click
        self._seed: str = seed
        self._pressed: bool = False
        self._badge_kind: str = badge_kind
        self._cover: QPixmap | None = cover
        self._key: str = ''
        self._top_color, self._bottom_color = cover_colors(seed or title)
        self._initial: str = self._initial_of(title)

        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        # 封面交给组件库的 ImageLabel：它按屏幕像素比缩放，高分屏下不发虚
        self.cover_label: ImageLabel = ImageLabel(self)
        self.cover_label.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.cover_label.setBorderRadius(
            CORNER_RADIUS, CORNER_RADIUS, CORNER_RADIUS, CORNER_RADIUS
        )
        self.cover_label.move(0, 0)
        self.cover_label.hide()

        self.overlay: _CardOverlay = _CardOverlay(self)
        self.overlay.move(0, 0)

        self.badge_label: CaptionLabel = CaptionLabel(self)
        self.badge_label.setVisible(False)
        self.badge_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.title_label: StrongBodyLabel = StrongBodyLabel(self)
        self.title_label.setText(title)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_font = self.title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        setCustomStyleSheet(
            self.title_label,
            'StrongBodyLabel { color: #ffffff; background: transparent; }',
            'StrongBodyLabel { color: #ffffff; background: transparent; }',
        )

        self.meta_label: CaptionLabel = CaptionLabel(self)
        self.meta_label.setText(meta_text)
        self.meta_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        setCustomStyleSheet(
            self.meta_label,
            'CaptionLabel { color: rgba(255, 255, 255, 0.80); background: transparent; }',
            'CaptionLabel { color: rgba(255, 255, 255, 0.80); background: transparent; }',
        )

        self.warning_label: CaptionLabel = CaptionLabel(self)
        self.warning_label.setVisible(False)
        self.warning_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.addWidget(self.badge_label)
        badge_row.addStretch(1)
        badge_row.addWidget(self.warning_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(2)
        layout.addLayout(badge_row)
        layout.addStretch(1)
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)

        if badge_text:
            self.set_badge(badge_text, badge_kind)

        self.set_cover(cover)

    # ------------------------------------------------------------------
    # 外部接口
    # ------------------------------------------------------------------

    @property
    def title(self) -> str:
        """卡片标题，供搜索过滤使用。"""
        return self.title_label.text()

    @property
    def key(self) -> str:
        """卡片绑定的插件标识，用于远程封面回填。"""
        return self._key

    @key.setter
    def key(self, value: str) -> None:
        self._key = value

    def set_badge(self, text: str, kind: str = BADGE_NONE) -> None:
        """设置左上角的实心状态标签，空文字表示不显示。"""
        self._badge_kind = kind
        self.badge_label.setText(text)
        self.badge_label.setVisible(bool(text))
        if not text:
            return

        light, dark = BADGE_COLORS.get(kind, BADGE_COLORS[BADGE_NONE])
        self.badge_label.adjustSize()
        self.badge_label.setFixedHeight(20)
        self.badge_label.setMinimumWidth(self.badge_label.width() + 16)
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setCustomStyleSheet(
            self.badge_label,
            f'CaptionLabel {{'
            f'  background-color: {light};'
            f'  color: #ffffff;'
            f'  border-radius: 10px;'
            f'  padding: 0 8px;'
            f'  font-size: 11px;'
            f'}}',
            f'CaptionLabel {{'
            f'  background-color: {dark};'
            f'  color: #ffffff;'
            f'  border-radius: 10px;'
            f'  padding: 0 8px;'
            f'  font-size: 11px;'
            f'}}',
        )

    def set_enabled_state(self, enabled: bool) -> None:
        """操作进行中时禁用点击。"""
        self.setEnabled(enabled)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor
        )

    def set_warning(self, text: str) -> None:
        """设置右上角的警示标签，空字符串表示隐藏。"""
        self.warning_label.setText(text)
        self.warning_label.setVisible(bool(text))
        if not text:
            return

        self.warning_label.adjustSize()
        self.warning_label.setFixedHeight(20)
        self.warning_label.setMinimumWidth(self.warning_label.width() + 16)
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setCustomStyleSheet(
            self.warning_label,
            'CaptionLabel {'
            '  background-color: #8a6d00;'
            '  color: #ffffff;'
            '  border-radius: 10px;'
            '  padding: 0 8px;'
            '  font-size: 11px;'
            '}',
            'CaptionLabel {'
            '  background-color: #8a6d00;'
            '  color: #ffffff;'
            '  border-radius: 10px;'
            '  padding: 0 8px;'
            '  font-size: 11px;'
            '}',
        )

    def set_cover(self, cover: QPixmap | None) -> None:
        """设置封面位图；传 None 时回退到按插件标识生成的渐变封面。

        Args:
            cover: 原始封面位图。这里保存原图，屏幕像素比变化时按新比例重裁。
        """
        self._cover = cover
        if cover is not None and not cover.isNull():
            self._refresh_cover_pixmap()
        else:
            self.cover_label.hide()
        self.update()

    def _refresh_cover_pixmap(self) -> None:
        """按当前设备像素比重裁原始封面并交给 cover_label。

        重裁始终基于 set_cover 保存的原始位图，反复跨屏也不会逐次缩放劣化。
        拿不到原始位图或位图尺寸为 0 时直接跳过，保持现有显示。
        """
        cover = self._cover
        if cover is None or cover.isNull():
            return
        if cover.width() <= 0 or cover.height() <= 0:
            return
        self.cover_label.setImage(self._fit_cover(cover))
        # ImageLabel.setImage 会把标签改成图片像素尺寸，这里压回卡片大小
        self.cover_label.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.cover_label.show()

    def event(self, event: QEvent) -> bool:
        """屏幕像素比变化时重新裁切封面。

        这里选 QEvent.Type.DevicePixelRatioChange，而不是监听窗口的
        screenChanged：该事件由 Qt 直接投递给受影响的控件，不用等
        windowHandle() 建好，也不用管窗口重建后重连信号；本环境
        PySide6 6.11.1 支持该事件（Qt 6.6 起提供）。

        Args:
            event: Qt 事件对象。

        Returns:
            是否已处理该事件；这里始终交回父类处理。
        """
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            # 事件到达时控件的 devicePixelRatioF() 已经是新值，重裁即可清晰
            self._refresh_cover_pixmap()
        return super().event(event)

    def _fit_cover(self, cover: QPixmap) -> QPixmap:
        """按卡片比例居中裁切封面。

        ImageLabel 会把图片拉伸铺满标签，所以要先裁成卡片比例，否则不同
        比例的封面会被压变形。裁切按屏幕像素比做，避免二次缩放发虚。
        """
        ratio = self.devicePixelRatioF()
        target = QSize(int(CARD_WIDTH * ratio), int(CARD_HEIGHT * ratio))
        scaled = cover.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - target.width()) // 2)
        y = max(0, (scaled.height() - target.height()) // 2)
        cropped = scaled.copy(x, y, target.width(), target.height())
        cropped.setDevicePixelRatio(ratio)
        return cropped

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        """没有封面时画按插件标识配色的渐变底；有封面时整块交给 ImageLabel。

        Args:
            event: Qt 绘制事件，本方法按控件自身尺寸重绘，不读取事件内容。
        """
        if self._cover is not None and not self._cover.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )

        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)
        painter.setClipPath(path)

        gradient = QLinearGradient(QPointF(0, 0), QPointF(rect.width(), rect.height()))
        gradient.setColorAt(0.0, self._top_color)
        gradient.setColorAt(1.0, self._bottom_color)
        painter.fillRect(rect, gradient)

        glow = QRadialGradient(
            QPointF(rect.width() * 0.72, rect.height() * 0.24),
            rect.width() * 0.62,
        )
        glow.setColorAt(0.0, QColor(255, 255, 255, 46))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(rect, glow)

        initial_font = QFont(self.font())
        initial_font.setPointSize(46)
        initial_font.setBold(True)
        painter.setFont(initial_font)
        painter.setPen(QColor(255, 255, 255, 26))
        painter.drawText(
            QRectF(0, 6, rect.width() - 20, rect.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            self._initial,
        )
        painter.end()

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------

    def enterEvent(self, event: QEnterEvent) -> None:
        self.overlay.set_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.overlay.set_hover(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        should_click = (
            self._pressed
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        )
        self._pressed = False
        super().mouseReleaseEvent(event)
        if should_click and self.isEnabled():
            self._emit_click()

    def _emit_click(self) -> None:
        if self._on_click is not None:
            self._on_click()
        else:
            self.clicked.emit()

    @staticmethod
    def _initial_of(text: str) -> str:
        value = (text or '').strip()
        return value[0].upper() if value else '?'


class PluginPager(QWidget):
    """卡片网格的分页条：上一页、第 x / y 页、下一页。"""

    page_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._page: int = 0
        self._count: int = 1

        self.prev_btn: TransparentToolButton = TransparentToolButton(
            FluentIcon.CARE_LEFT_SOLID, self
        )
        self.prev_btn.setFixedSize(28, 28)
        self.prev_btn.clicked.connect(self._go_prev)

        self.page_label: CaptionLabel = CaptionLabel(self)
        self.page_label.setTextColor('#8a8a8a', '#9a9a9a')
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(72)

        self.next_btn: TransparentToolButton = TransparentToolButton(
            FluentIcon.CARE_RIGHT_SOLID, self
        )
        self.next_btn.setFixedSize(28, 28)
        self.next_btn.clicked.connect(self._go_next)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.page_label)
        layout.addWidget(self.next_btn)

        self._sync()

    @property
    def current_page(self) -> int:
        """当前页序号，从 0 开始。"""
        return self._page

    def set_page_count(self, count: int) -> None:
        """设置总页数，页码越界时收敛到最后一页。"""
        self._count = max(1, count)
        self._page = min(self._page, self._count - 1)
        self._sync()

    def set_current_page(self, index: int) -> None:
        """直接跳到指定页，不发出 page_changed。"""
        self._page = max(0, min(index, self._count - 1))
        self._sync()

    def _go_prev(self) -> None:
        if self._page <= 0:
            return
        self._page -= 1
        self._sync()
        self.page_changed.emit(self._page)

    def _go_next(self) -> None:
        if self._page >= self._count - 1:
            return
        self._page += 1
        self._sync()
        self.page_changed.emit(self._page)

    def _sync(self) -> None:
        """刷新页码文字与按钮可用状态。"""
        self.page_label.setText(f'{self._page + 1} / {self._count}')
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < self._count - 1)
        self.setVisible(self._count > 1)


class PluginCardGrid(QWidget):
    """卡片网格容器。"""

    resized = Signal()
    """网格尺寸变化信号，供分页按新的宽度重算每页数量。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[PluginCard] = []
        self._layout: FlowLayout = FlowLayout(self, needAni=False, isTight=True)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(12)
        self._layout.setVerticalSpacing(12)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.resized.emit()

    @property
    def cards(self) -> list[PluginCard]:
        return list(self._cards)

    def clear(self) -> None:
        """移除并销毁全部卡片。"""
        for card in self._cards:
            self._layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

    def add_card(self, card: PluginCard) -> None:
        self._cards.append(card)
        self._layout.addWidget(card)

    def apply_visible(self, cards: list[PluginCard]) -> None:
        """只显示给定的卡片，其余隐藏并退出布局占位。

        Args:
            cards: 需要在当前页显示的卡片。
        """
        visible = {id(card) for card in cards}
        for card in self._cards:
            card.setVisible(id(card) in visible)
        self._layout.invalidate()
        self.updateGeometry()
