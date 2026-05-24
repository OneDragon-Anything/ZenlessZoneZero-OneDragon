from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import Theme, qconfig

from zzz_od.config.dodge_stats_config import STATS_DISPLAY_APPS

# 统计项分类
STATS_CATEGORIES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ('overview', '综合', [
        ('one_dragon', '一条龙'),
        ('dodge', '格挡'),
    ]),
    ('daily', '日常', [
        ('charge_plan', '体力刷本'),
        ('coffee', '咖啡店'),
        ('scratch_card', '刮刮卡'),
        ('random_play', '录像店营业'),
        ('email', '邮件'),
        ('redemption_code', '兑换码'),
        ('engagement_reward', '活跃度奖励'),
    ]),
    ('combat', '战斗', [
        ('lost_void', '迷失之地'),
        ('withered_domain', '枯萎之都'),
        ('trigrams_collection', '卦象集录'),
        ('notorious_hunt', '恶名狩猎'),
        ('shiyu_defense', '式舆防卫战'),
        ('life_on_line', '真·拿命验收'),
        ('world_patrol', '锄大地'),
    ]),
    ('other', '其他', [
        ('suibian_temple', '随便观'),
        ('city_fund', '丽都城募'),
        ('ridu_weekly', '丽都周纪'),
        ('intel_board', '情报板'),
        ('drive_disc_dismantle', '驱动盘拆解'),
    ]),
]


def _get_stats_bar_palette() -> dict:
    """返回统计栏的主题色配置"""
    if qconfig.theme == Theme.DARK:
        return {
            'tint': QColor(18, 20, 30, 190),
            'title': QColor(255, 219, 41, 220),
            'text': QColor(210, 210, 215, 200),
            'number': QColor(255, 255, 255, 230),
            'dim': QColor(150, 150, 155, 140),
            'border': QColor(255, 255, 255, 25),
            'cat_bg': QColor(255, 255, 255, 12),
        }
    return {
        'tint': QColor(22, 24, 35, 195),
        'title': QColor(255, 219, 41, 220),
        'text': QColor(210, 210, 215, 200),
        'number': QColor(255, 255, 255, 230),
        'dim': QColor(150, 150, 155, 140),
        'border': QColor(255, 255, 255, 20),
        'cat_bg': QColor(255, 255, 255, 10),
    }


class StatsBarBackground(QWidget):
    """半透明磨砂背景层，跟随 StatsBar 大小"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.tint: QColor = QColor(22, 24, 35, 195)
        self.border_color: QColor = QColor(255, 255, 255, 20)
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


class _StatCell(QWidget):
    """单个统计项：名称 + 数字，紧凑排列"""

    def __init__(
        self,
        name: str,
        count: int,
        palette: dict,
        is_highlight: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        num_font = QFont("Microsoft YaHei", 14, QFont.Weight.Bold)
        name_font = QFont("Microsoft YaHei", 9)

        number_color = (
            palette['title'].name(QColor.NameFormat.HexArgb)
            if is_highlight
            else palette['number'].name(QColor.NameFormat.HexArgb)
        )
        name_color = palette['dim'].name(QColor.NameFormat.HexArgb)

        num_label = QLabel(str(count))
        num_label.setFont(num_font)
        num_label.setStyleSheet(
            f'color: {number_color}; border: none;'
        )
        num_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(num_label)

        name_label = QLabel(name)
        name_label.setFont(name_font)
        name_label.setStyleSheet(
            f'color: {name_color}; border: none;'
        )
        name_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(name_label)


class StatsBar(QWidget):
    """主页半透明统计卡片，按分类多列展示陪伴数据"""

    def __init__(self, user_stats, parent: QWidget | None = None):
        super().__init__(parent)
        self.user_stats = user_stats
        self._children_to_clean: list[QWidget] = []
        self._bg: StatsBarBackground | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedWidth(589)

        self._bg = StatsBarBackground(self)
        self._bg.stackUnder(self)

        self._build_items()

    def _get_count(self, key: str) -> int:
        """获取统计计数，兼容一条龙/格挡和应用计数"""
        if key == 'one_dragon':
            return self.user_stats.one_dragon_count
        if key == 'dodge':
            return self.user_stats.dodge_count
        return self.user_stats.get_app_count(key)

    def _build_items(self) -> None:
        """构建卡片内容"""
        # 清除旧内容
        for w in self._children_to_clean:
            w.setParent(None)
            w.deleteLater()
        self._children_to_clean.clear()

        # 移除旧 layout
        old_layout = self.layout()
        if old_layout is not None:
            QWidget().setLayout(old_layout)

        palette = _get_stats_bar_palette()

        # 检查是否有数据
        total_count = (
            self.user_stats.one_dragon_count
            + self.user_stats.dodge_count
        )
        for app_id in STATS_DISPLAY_APPS:
            total_count += self.user_stats.get_app_count(app_id)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)

        if total_count == 0:
            # 无数据时的占位
            placeholder = QLabel('陪伴记录将在运行后显示')
            placeholder.setFont(QFont("Microsoft YaHei", 10))
            dim_color = palette['dim'].name(QColor.NameFormat.HexArgb)
            placeholder.setStyleSheet(f'color: {dim_color}; border: none;')
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(placeholder)
            self._children_to_clean.append(placeholder)
            self.setFixedHeight(44)
            return

        # 标题行
        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        title_label = QLabel('陪伴记录')
        title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title_color = palette['title'].name(QColor.NameFormat.HexArgb)
        title_label.setStyleSheet(f'color: {title_color}; border: none;')
        title_row.addWidget(title_label)
        title_row.addStretch()
        outer.addLayout(title_row)
        self._children_to_clean.append(title_label)

        # 分类区域
        for _cat_key, cat_name, items in STATS_CATEGORIES:
            # 计算该分类是否有数据
            cat_total = sum(self._get_count(k) for k, _ in items)
            if cat_total == 0:
                continue

            # 分类标题
            cat_title = QLabel(cat_name)
            cat_title.setFont(QFont("Microsoft YaHei", 9))
            dim = palette['dim'].name(QColor.NameFormat.HexArgb)
            cat_title.setStyleSheet(f'color: {dim}; border: none;')
            outer.addWidget(cat_title)
            self._children_to_clean.append(cat_title)

            # 网格：每行最多 4 个 cell
            grid = QGridLayout()
            grid.setSpacing(8, 4)
            grid.setContentsMargins(8, 0, 8, 2)

            col = 0
            row = 0
            cols_per_row = 4
            for key, name in items:
                count = self._get_count(key)
                if count == 0:
                    continue
                is_hl = (key == 'one_dragon' or key == 'dodge')
                cell = _StatCell(name, count, palette, is_highlight=is_hl)
                grid.addWidget(cell, row, col)
                self._children_to_clean.append(cell)
                col += 1
                if col >= cols_per_row:
                    col = 0
                    row += 1

            outer.addLayout(grid)

        self.setFixedHeight(self.sizeHint().height() + 20)

    def refresh(self) -> None:
        """刷新统计数据"""
        self._build_items()

    def resizeEvent(self, event) -> None:
        if self._bg:
            self._bg.setGeometry(self.rect())
        super().resizeEvent(event)
