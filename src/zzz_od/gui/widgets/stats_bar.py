from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import Theme, qconfig

from one_dragon_qt.services.theme_manager import ThemeManager
from zzz_od.config.dodge_stats_config import (
    STATS_DISPLAY_APPS,  # noqa: F401 - used by other modules
)

if TYPE_CHECKING:
    from zzz_od.config.dodge_stats_config import UserStatsConfig

# 所有可统计项目，按重要度排序
STATS_ITEMS: list[tuple[str, str]] = [
    ('one_dragon', '一条龙'),
    ('dodge', '格挡'),
    ('charge_plan', '体力刷本'),
    ('lost_void', '迷失之地'),
    ('withered_domain', '枯萎之都'),
    ('trigrams_collection', '卦象集录'),
    ('notorious_hunt', '恶名狩猎'),
    ('world_patrol', '锄大地'),
    ('shiyu_defense', '式舆防卫战'),
    ('random_play', '录像店营业'),
    ('coffee', '咖啡店'),
    ('scratch_card', '刮刮卡'),
    ('suibian_temple', '随便观'),
    ('life_on_line', '真·拿命验收'),
    ('city_fund', '丽都城募'),
    ('ridu_weekly', '丽都周纪'),
    ('intel_board', '情报板'),
    ('email', '邮件'),
    ('redemption_code', '兑换码'),
    ('engagement_reward', '活跃度奖励'),
    ('drive_disc_dismantle', '驱动盘拆解'),
]


def _get_stats_bar_palette() -> dict:
    """返回统计栏的主题色配置，高亮色跟随全局主题色"""
    theme_qcolor = ThemeManager.get_qcolor()
    # 高亮色：主题色 + 适当透明度
    hl_color = QColor(theme_qcolor)
    hl_color.setAlpha(230)

    if qconfig.theme == Theme.DARK:
        return {
            'tint': QColor(18, 20, 30, 190),
            'title': hl_color,
            'number': QColor(255, 255, 255, 230),
            'dim': QColor(150, 150, 155, 140),
            'border': QColor(255, 255, 255, 25),
        }
    return {
        'tint': QColor(22, 24, 35, 195),
        'title': hl_color,
        'number': QColor(255, 255, 255, 230),
        'dim': QColor(150, 150, 155, 140),
        'border': QColor(255, 255, 255, 20),
    }


class StatsBarBackground(QWidget):
    """半透明磨砂背景层，跟随 StatsBar 大小"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.tint: QColor = QColor(22, 24, 35, 195)
        self.border_color: QColor = QColor(255, 255, 255, 20)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )

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
    """主页半透明统计卡片，多列网格展示陪伴数据"""

    COLS = 5

    def __init__(self, user_stats: UserStatsConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self.user_stats = user_stats
        self._bg: StatsBarBackground | None = None
        self._cleanups: list[QWidget] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.setFixedWidth(589)
        # 不设固定高度，让布局自动撑开
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum
        )

        self._bg = StatsBarBackground(self)
        self._bg.stackUnder(self)

        self._build_items()

    def _get_count(self, key: str) -> int:
        """获取统计计数"""
        if key == 'one_dragon':
            return self.user_stats.one_dragon_count
        if key == 'dodge':
            return self.user_stats.dodge_count
        return self.user_stats.get_app_count(key)

    def _clear_layout(self) -> None:
        """清除所有子控件和旧布局"""
        for w in self._cleanups:
            w.setParent(None)
            w.deleteLater()
        self._cleanups.clear()

        old = self.layout()
        if old is not None:
            QWidget().setLayout(old)

    def _build_items(self) -> None:
        """构建卡片内容"""
        self._clear_layout()
        palette = _get_stats_bar_palette()

        # 将主题色同步到背景层
        if self._bg is not None:
            self._bg.tint = palette['tint']
            self._bg.border_color = palette['border']
            self._bg.update()

        # 收集有数据的项目
        active: list[tuple[str, str, int]] = []
        for key, name in STATS_ITEMS:
            c = self._get_count(key)
            if c > 0:
                active.append((key, name, c))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(4)
        outer.setSizeConstraint(
            QVBoxLayout.SizeConstraint.SetMinAndMaxSize
        )

        dim_color = palette['dim'].name(QColor.NameFormat.HexArgb)

        if not active:
            placeholder = QLabel('一条龙已为您完成的内容将在运行后显示')
            placeholder.setFont(QFont("Microsoft YaHei", 9))
            placeholder.setStyleSheet(
                f'color: {dim_color}; border: none;'
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(placeholder)
            self._cleanups.append(placeholder)
            return

        # 标题行
        title_label = QLabel('一条龙已为您完成')
        title_label.setFont(
            QFont("Microsoft YaHei", 9, QFont.Weight.Bold)
        )
        title_color = palette['title'].name(QColor.NameFormat.HexArgb)
        title_label.setStyleSheet(
            f'color: {title_color}; border: none;'
        )
        outer.addWidget(title_label)
        self._cleanups.append(title_label)

        # 副标题行：首次使用日期 + 游戏运行时间 + 电量消耗 + 总运行次数
        subtitle_parts: list[str] = []
        first_date = self.user_stats.first_use_date
        if first_date:
            subtitle_parts.append(f'自 {first_date}')
        play_minutes = self.user_stats.game_play_minutes
        if play_minutes > 0:
            hours, mins = divmod(play_minutes, 60)
            if hours > 0:
                subtitle_parts.append(f'陪伴绝区零 {hours}小时{mins}分钟')
            else:
                subtitle_parts.append(f'陪伴绝区零 {mins}分钟')
        charge_power = self.user_stats.total_charge_power
        if charge_power > 0:
            subtitle_parts.append(f'消耗 {charge_power} 电量')
        total_runs = self.user_stats.total_run_count
        if total_runs > 0:
            subtitle_parts.append(f'共运行 {total_runs} 次')
        if subtitle_parts:
            subtitle_label = QLabel('  ·  '.join(subtitle_parts))
            subtitle_label.setFont(QFont("Microsoft YaHei", 8))
            subtitle_label.setStyleSheet(
                f'color: {dim_color}; border: none;'
            )
            outer.addWidget(subtitle_label)
            self._cleanups.append(subtitle_label)

        # 网格
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(2)
        grid.setContentsMargins(4, 0, 4, 0)

        num_font = QFont("Microsoft YaHei", 12, QFont.Weight.Bold)
        name_font = QFont("Microsoft YaHei", 8)
        num_color = palette['number'].name(QColor.NameFormat.HexArgb)
        hl_color = palette['title'].name(QColor.NameFormat.HexArgb)

        row = 0
        col = 0
        for key, name, count in active:
            is_hl = key in ('one_dragon', 'dodge')
            color = hl_color if is_hl else num_color

            num_lbl = QLabel(str(count))
            num_lbl.setFont(num_font)
            num_lbl.setStyleSheet(f'color: {color}; border: none;')
            num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(num_lbl, row * 2, col)
            self._cleanups.append(num_lbl)

            name_lbl = QLabel(name)
            name_lbl.setFont(name_font)
            name_lbl.setStyleSheet(f'color: {dim_color}; border: none;')
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(name_lbl, row * 2 + 1, col)
            self._cleanups.append(name_lbl)

            col += 1
            if col >= self.COLS:
                col = 0
                row += 1

        outer.addLayout(grid)

    def refresh(self) -> None:
        """刷新统计数据"""
        self._build_items()
        self.updateGeometry()

    def resizeEvent(self, event) -> None:
        if self._bg:
            self._bg.setGeometry(self.rect())
        super().resizeEvent(event)
