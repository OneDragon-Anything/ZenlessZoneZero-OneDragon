from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget
from qfluentwidgets import Theme, qconfig

from zzz_od.config.dodge_stats_config import STATS_DISPLAY_APPS


def _get_stats_bar_palette() -> dict:
    """返回统计栏的主题色配置"""
    if qconfig.theme == Theme.DARK:
        return {
            'tint': QColor(18, 20, 30, 160),
            'text': QColor(220, 220, 225, 220),
            'accent': QColor(255, 219, 41, 200),
            'border': QColor(255, 255, 255, 30),
        }
    return {
        'tint': QColor(22, 24, 35, 150),
        'text': QColor(220, 220, 225, 220),
        'accent': QColor(255, 219, 41, 200),
        'border': QColor(255, 255, 255, 25),
    }


class StatsBarBackground(QWidget):
    """半透明磨砂背景层，跟随 StatsBar 大小"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.tint: QColor = QColor(22, 24, 35, 150)
        self.border_color: QColor = QColor(255, 255, 255, 25)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rectF = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rectF, 8, 8)

        painter.fillPath(path, self.tint)
        painter.setPen(self.border_color)
        painter.drawPath(path)


class StatsBar(QWidget):
    """主页半透明统计栏，展示陪伴数据"""

    def __init__(self, user_stats, parent: QWidget | None = None):
        super().__init__(parent)
        self.user_stats = user_stats
        self._items: list[tuple[str, QLabel]] = []
        self._bg: StatsBarBackground | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(0)

        self._bg = StatsBarBackground(self)
        self._bg.stackUnder(self)

        self._build_items()

    def _build_items(self) -> None:
        """根据当前统计数据构建显示项"""
        layout = self.layout()

        # 清除旧项
        for _, label in self._items:
            layout.removeWidget(label)
            label.deleteLater()
        self._items.clear()

        stats = self.user_stats
        palette = _get_stats_bar_palette()
        accent_color = palette['accent'].name(QColor.NameFormat.HexArgb)
        text_color = palette['text'].name(QColor.NameFormat.HexArgb)

        font = QFont("Microsoft YaHei", 10)

        # 优先显示有数据的项目，最多显示 8 项
        items_to_show: list[tuple[str, int]] = []

        # 格挡和一条龙始终显示
        od_count = stats.one_dragon_count
        dodge_count = stats.dodge_count
        if od_count > 0:
            items_to_show.append((f'一条龙 {od_count} 次', od_count))
        if dodge_count > 0:
            items_to_show.append((f'格挡 {dodge_count} 次', dodge_count))

        # 各应用统计
        for app_id, app_name in STATS_DISPLAY_APPS.items():
            count = stats.get_app_count(app_id)
            if count > 0:
                items_to_show.append((f'{app_name} {count} 次', count))

        # 按次数降序排列
        items_to_show.sort(key=lambda x: x[1], reverse=True)

        # 最多显示 8 项
        items_to_show = items_to_show[:8]

        if not items_to_show:
            label = QLabel('开始你的冒险旅程吧')
            label.setFont(font)
            label.setStyleSheet(f'color: {text_color}; border: none;')
            self.layout().addWidget(label)
            self._items.append(('', label))
            return

        for i, (text, _) in enumerate(items_to_show):
            label = QLabel(text)
            label.setFont(font)
            # 第一项使用强调色，其余使用普通色
            if i == 0:
                label.setStyleSheet(
                    f'color: {accent_color}; font-weight: bold; border: none;'
                )
            else:
                label.setStyleSheet(f'color: {text_color}; border: none;')
            self.layout().addWidget(label)
            self._items.append((text, label))

            # 分隔符
            if i < len(items_to_show) - 1:
                sep = QLabel('·')
                sep.setFont(font)
                sep.setStyleSheet(
                    f'color: {text_color}; border: none;'
                    f' margin-left: 6px; margin-right: 6px;'
                )
                self.layout().addWidget(sep)
                self._items.append(('', sep))

    def refresh(self) -> None:
        """刷新统计数据"""
        self._build_items()

    def resizeEvent(self, event) -> None:
        if self._bg:
            self._bg.setGeometry(self.rect())
        super().resizeEvent(event)
