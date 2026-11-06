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


def _make_stat_label(
    text: str,
    font: QFont,
    color: str,
    alignment: Qt.AlignmentFlag | None = None,
) -> QLabel:
    """按统计栏统一样式创建 QLabel（alignment 传 None 保持默认对齐）"""
    lbl = QLabel(text)
    lbl.setFont(font)
    lbl.setStyleSheet(f'color: {color}; border: none;')
    if alignment is not None:
        lbl.setAlignment(alignment)
    return lbl


def _build_subtitle_parts(user_stats) -> list[str]:
    """副标题文案：首次使用日期 + 游戏运行时间 + 电量消耗 + 总运行次数"""
    parts: list[str] = []
    first_date = user_stats.first_use_date
    if first_date:
        parts.append(f'自 {first_date}')
    play_minutes = user_stats.game_play_minutes
    if play_minutes > 0:
        hours, mins = divmod(play_minutes, 60)
        if hours > 0:
            parts.append(f'陪伴绝区零 {hours}小时{mins}分钟')
        else:
            parts.append(f'陪伴绝区零 {mins}分钟')
    charge_power = user_stats.total_charge_power
    if charge_power > 0:
        parts.append(f'消耗 {charge_power} 电量')
    total_runs = user_stats.total_run_count
    if total_runs > 0:
        parts.append(f'共运行 {total_runs} 次')
    return parts


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

    def __init__(self, user_stats, parent: QWidget | None = None):
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

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(4)
        outer.setSizeConstraint(
            QVBoxLayout.SizeConstraint.SetMinAndMaxSize
        )

        active = self._collect_active_items()

        if not active:
            self._append_placeholder(outer, palette)
            return

        self._append_title(outer, palette)
        self._append_subtitle(outer, palette)
        self._append_grid(outer, palette, active)

    def _collect_active_items(self) -> list[tuple[str, str, int]]:
        """收集有数据的项目"""
        active: list[tuple[str, str, int]] = []
        for key, name in STATS_ITEMS:
            c = self._get_count(key)
            if c > 0:
                active.append((key, name, c))
        return active

    def _append_placeholder(self, outer: QVBoxLayout, palette: dict) -> None:
        """无数据时的占位文案"""
        dim_color = palette['dim'].name(QColor.NameFormat.HexArgb)
        placeholder = _make_stat_label(
            '一条龙已为您完成的内容将在运行后显示',
            QFont("Microsoft YaHei", 9), dim_color,
            Qt.AlignmentFlag.AlignCenter,
        )
        outer.addWidget(placeholder)
        self._cleanups.append(placeholder)

    def _append_title(self, outer: QVBoxLayout, palette: dict) -> None:
        """标题行"""
        title_color = palette['title'].name(QColor.NameFormat.HexArgb)
        title_label = _make_stat_label(
            '一条龙已为您完成',
            QFont("Microsoft YaHei", 9, QFont.Weight.Bold), title_color,
        )
        outer.addWidget(title_label)
        self._cleanups.append(title_label)

    def _append_subtitle(self, outer: QVBoxLayout, palette: dict) -> None:
        """副标题行：首次使用日期 + 游戏运行时间 + 电量消耗 + 总运行次数"""
        parts = _build_subtitle_parts(self.user_stats)
        if not parts:
            return
        dim_color = palette['dim'].name(QColor.NameFormat.HexArgb)
        subtitle_label = _make_stat_label(
            '  ·  '.join(parts), QFont("Microsoft YaHei", 8), dim_color,
        )
        outer.addWidget(subtitle_label)
        self._cleanups.append(subtitle_label)

    def _append_grid(
        self,
        outer: QVBoxLayout,
        palette: dict,
        active: list[tuple[str, str, int]],
    ) -> None:
        """多列网格：每个项目上数字下名称，一条龙/格挡高亮"""
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(2)
        grid.setContentsMargins(4, 0, 4, 0)

        num_font = QFont("Microsoft YaHei", 12, QFont.Weight.Bold)
        name_font = QFont("Microsoft YaHei", 8)
        num_color = palette['number'].name(QColor.NameFormat.HexArgb)
        hl_color = palette['title'].name(QColor.NameFormat.HexArgb)
        dim_color = palette['dim'].name(QColor.NameFormat.HexArgb)

        for idx, (key, name, count) in enumerate(active):
            row, col = divmod(idx, self.COLS)
            is_hl = key in ('one_dragon', 'dodge')
            color = hl_color if is_hl else num_color

            num_lbl = _make_stat_label(
                str(count), num_font, color, Qt.AlignmentFlag.AlignCenter,
            )
            grid.addWidget(num_lbl, row * 2, col)
            self._cleanups.append(num_lbl)

            name_lbl = _make_stat_label(
                name, name_font, dim_color, Qt.AlignmentFlag.AlignCenter,
            )
            grid.addWidget(name_lbl, row * 2 + 1, col)
            self._cleanups.append(name_lbl)

        outer.addLayout(grid)

    def refresh(self) -> None:
        """刷新统计数据"""
        self._build_items()
        self.updateGeometry()

    def resizeEvent(self, event) -> None:
        if self._bg:
            self._bg.setGeometry(self.rect())
        super().resizeEvent(event)
