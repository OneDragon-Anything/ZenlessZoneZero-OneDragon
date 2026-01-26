from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    FlyoutViewBase,
    TeachingTip,
    TeachingTipTailPosition,
    TransparentToolButton,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.combo_box import ComboBox
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.intel_board import intel_board_const
from zzz_od.application.intel_board.intel_board_config import IntelBoardConfig

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class IntelBoardSettingFlyout(FlyoutViewBase):
    """情报板配置弹出框"""

    _current_tip: TeachingTip | None = None

    def __init__(self, ctx: ZContext, group_id: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.group_id = group_id
        self.intel_board_config: IntelBoardConfig | None = None
        self._setup_ui()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 12)
        layout.setSpacing(8)

        # 关闭按钮行（顶部）
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.closeButton = TransparentToolButton(FluentIcon.CLOSE)
        self.closeButton.setFixedSize(24, 24)
        self.closeButton.setIconSize(QSize(10, 10))
        close_row.addWidget(self.closeButton)
        layout.addLayout(close_row)

        # 预备编队行
        team_row = QHBoxLayout()
        team_row.setSpacing(8)
        team_label = CaptionLabel(gt('预备编队'))
        team_label.setFixedWidth(60)
        self.predefined_team_opt = ComboBox()
        self.predefined_team_opt.setFixedWidth(120)
        self.predefined_team_opt.currentIndexChanged.connect(self._on_team_changed)
        team_row.addWidget(team_label)
        team_row.addWidget(self.predefined_team_opt)
        team_row.addStretch(1)
        layout.addLayout(team_row)

        # 自动战斗行
        self.auto_battle_row = QHBoxLayout()
        self.auto_battle_row.setSpacing(8)
        self.auto_battle_label = CaptionLabel(gt('自动战斗'))
        self.auto_battle_label.setFixedWidth(60)
        self.auto_battle_opt = ComboBox()
        self.auto_battle_opt.setFixedWidth(120)
        self.auto_battle_opt.currentIndexChanged.connect(self._on_auto_battle_changed)
        self.auto_battle_row.addWidget(self.auto_battle_label)
        self.auto_battle_row.addWidget(self.auto_battle_opt)
        self.auto_battle_row.addStretch(1)
        layout.addLayout(self.auto_battle_row)

    def init_config(self):
        """初始化配置"""
        self.intel_board_config = self.ctx.run_context.get_config(
            app_id=intel_board_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

        # 初始化预备编队下拉框
        team_list = ([ConfigItem('游戏内配队', -1)] +
                     [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.predefined_team_opt.set_items(team_list, self.intel_board_config.predefined_team_idx)

        # 初始化自动战斗下拉框
        auto_battle_list = get_auto_battle_op_config_list(sub_dir='auto_battle')
        self.auto_battle_opt.set_items(auto_battle_list, self.intel_board_config.auto_battle_config)

        # 根据当前配队设置自动战斗选项的可见性
        self._update_auto_battle_visibility()

    def _on_team_changed(self, idx: int) -> None:
        value = self.predefined_team_opt.currentData()
        if self.intel_board_config:
            self.intel_board_config.predefined_team_idx = value
        self._update_auto_battle_visibility()

    def _update_auto_battle_visibility(self):
        """更新自动战斗选项的可见性"""
        visible = self.intel_board_config and self.intel_board_config.predefined_team_idx == -1
        self.auto_battle_label.setVisible(visible)
        self.auto_battle_opt.setVisible(visible)

    def _on_auto_battle_changed(self, idx: int) -> None:
        if self.intel_board_config:
            self.intel_board_config.auto_battle_config = self.auto_battle_opt.currentData()

    @classmethod
    def show_flyout(cls, ctx: ZContext, group_id: str, target: QWidget, parent: QWidget | None = None) -> TeachingTip:
        """显示配置弹出框"""
        # 关闭现有的弹出框
        if cls._current_tip is not None:
            cls._current_tip.close()

        # 创建弹出框视图
        content_view = IntelBoardSettingFlyout(ctx, group_id, parent)
        content_view.init_config()

        # 创建并显示 TeachingTip
        tip = TeachingTip.make(
            view=content_view,
            target=target,
            duration=-1,
            tailPosition=TeachingTipTailPosition.RIGHT,
            parent=parent
        )

        cls._current_tip = tip
        content_view.closeButton.clicked.connect(tip.close)

        return tip
