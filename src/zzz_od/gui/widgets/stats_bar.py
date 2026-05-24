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

from zzz_od.config.dodge_stats_config import STATS_DISPLAY_APPS  # noqa: F401 - used by other modules

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
    """返回统计栏的主题色配置"""
    if qconfig.theme == Theme.DARK:
        return {
            'tint': QColor(18, 20, 30, 190),
            'title': QColor(255, 219, 41, 220),
            'number': QColor(255, 255, 255, 230),
            'dim': QColor(150, 150, 155, 140),
            'border': QColor(255, 255, 255, 25),
        }
    return {
        'tint': QColor(22, 24, 35, 195),
        'title': QColor(255, 219, 41, 220),
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

    # 每行显示的列数
    COLS = 5

    def __init__(self, user_stats, parent: QWidget | None = None):
        super().__init__(parent)
        self.user_stats = user_stats
        self._bg: StatsBarBackground | None = None
        self._cleanups: list[QWidget] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.setFixedWidth(589)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum
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

        # 收集有数据的项目
        active: list[tuple[str, str, int]] = []
        for key, name in STATS_ITEMS:
            c = self._get_count(key)
            if c > 0:
                active.append((key, name, c))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(4)

        dim_color = palette['dim'].name(QColor.NameFormat.HexArgb)

        if not active:
            placeholder = QLabel('陪伴记录将在运行后显示')
            placeholder.setFont(QFont("Microsoft YaHei", 9))
            placeholder.setStyleSheet(
                f'color: {dim_color}; border: none;'
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(placeholder)
            self._cleanups.append(placeholder)
            self.setFixedHeight(36)
            return

        # 标题行
        title_label = QLabel('陪伴记录')
        title_label.setFont(
            QFont("Microsoft YaHei", 9, QFont.Weight.Bold)
        )
        title_color = palette['title'].name(QColor.NameFormat.HexArgb)
        title_label.setStyleSheet(
            f'color: {title_color}; border: none;'
        )
        outer.addWidget(title_label)
        self._cleanups.append(title_label)

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

        # 强制激活布局后设置固定高度
        outer.activate()
        self.setFixedHeight(outer.sizeHint().height() + 12)

    def refresh(self) -> None:
        """刷新统计数据"""
        self._build_items()

    def resizeEvent(self, event) -> None:
        if self._bg:
            self._bg.setGeometry(self.rect())
        super().resizeEvent(event)
