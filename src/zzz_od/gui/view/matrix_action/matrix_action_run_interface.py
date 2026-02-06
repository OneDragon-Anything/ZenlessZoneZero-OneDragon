from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PushSettingCard

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application import application_const
from one_dragon.utils.log_utils import log
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidChallengeConfig,
    get_all_lost_void_challenge_config,
)
from zzz_od.application.matrix_action import matrix_action_const
from zzz_od.application.matrix_action.matrix_action_config import MatrixActionConfig
from zzz_od.application.matrix_action.matrix_action_run_record import (
    MatrixActionRunRecord,
)
from zzz_od.context.zzz_context import ZContext


class MatrixActionRunInterface(AppRunInterface):

    def __init__(
        self,
        ctx: ZContext,
        parent=None,
    ):
        self.ctx: ZContext = ctx
        self.config: Optional[MatrixActionConfig] = None
        self.run_record: Optional[MatrixActionRunRecord] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=matrix_action_const.APP_ID,
            object_name="matrix_action_run_interface",
            nav_text_cn="矩阵行动",
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        col_widget = QWidget(self)
        col_layout = QHBoxLayout(col_widget)
        col_widget.setLayout(col_layout)

        col_layout.addWidget(self._get_left_opts(), stretch=1)
        col_layout.addWidget(self._get_right_opts(), stretch=1)

        return col_widget

    def _get_left_opts(self) -> QWidget:
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_widget.setLayout(left_layout)

        self.help_opt = HelpCard(url="https://one-dragon.com/zzz/zh/docs/feat_hollow_zero.html")
        left_layout.addWidget(self.help_opt)

        self.challenge_config_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title="挑战配置",
            content="选择角色、编队等",
        )
        left_layout.addWidget(self.challenge_config_opt)

        self.team_name_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title="编队配置",
            content="选择预设备队",
        )
        left_layout.addWidget(self.team_name_opt)

        self.daily_plan_times_opt = SpinBoxSettingCard(
            icon=FluentIcon.CALENDAR,
            title="每天进入次数",
            content="分摊到每天运行",
        )
        left_layout.addWidget(self.daily_plan_times_opt)

        left_layout.addStretch(1)
        return left_widget

    def _get_right_opts(self) -> QWidget:
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_widget.setLayout(right_layout)

        self.run_record_opt = PushSettingCard(
            icon=FluentIcon.SYNC,
            title="运行记录",
            text="重置记录",
        )
        self.run_record_opt.clicked.connect(self._on_reset_record_clicked)
        right_layout.addWidget(self.run_record_opt)

        self.weekly_plan_times_opt = SpinBoxSettingCard(
            icon=FluentIcon.CALENDAR,
            title="每周进入次数",
            content="每周最多进入次数",
        )
        right_layout.addWidget(self.weekly_plan_times_opt)

        right_layout.addStretch(1)
        return right_widget

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)

        self.config = self.ctx.run_context.get_config(
            app_id=matrix_action_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=matrix_action_const.APP_ID,
        )

        self._update_challenge_config_options()
        self._update_team_options()

        self.challenge_config_opt.init_with_adapter(get_prop_adapter(self.config, "challenge_config"))
        self.team_name_opt.init_with_adapter(get_prop_adapter(self.config, "team_name"))
        self.daily_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, "daily_plan_times"))
        self.weekly_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, "weekly_plan_times"))

        self._update_run_record_display()

    def _update_challenge_config_options(self) -> None:
        config_list: list[LostVoidChallengeConfig] = get_all_lost_void_challenge_config()
        self.challenge_config_opt.set_options_by_list(
            [ConfigItem(config.module_name, config.module_name) for config in config_list]
        )

    def _update_team_options(self) -> None:
        team_list = self.ctx.team_config.team_list
        self.team_name_opt.set_options_by_list(
            [ConfigItem(team.name, team.name) for team in team_list]
        )

    def _update_run_record_display(self) -> None:
        if self.run_record.is_finished_by_week():
            content = "已达到每周进入上限 如错误可重置"
        elif self.run_record.is_finished_by_day():
            content = "已达到今日进入上限 如错误可重置"
        else:
            content = "进入次数 本日: %d, 本周: %d" % (
                self.run_record.daily_run_times,
                self.run_record.weekly_run_times,
            )
        self.run_record_opt.setContent(content)

    def _on_reset_record_clicked(self) -> None:
        self.run_record.reset_record()
        self.run_record.reset_for_weekly()
        log.info("重置成功")
        self._update_run_record_display()

    def _on_context_state_changed(self) -> None:
        AppRunInterface.on_context_state_changed(self)
        self._update_run_record_display()

