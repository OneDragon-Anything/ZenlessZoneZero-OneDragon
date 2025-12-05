from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PushSettingCard

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application import application_const
from one_dragon.utils.log_utils import log
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidChallengeConfig,
    get_all_lost_void_challenge_config,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_config import (
    LostVoidConfig,
    LostVoidTaskEnum,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_run_record import (
    LostVoidRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class LostVoidSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext):
        super().__init__(
            content_widget=None,
            object_name="lost_void_setting_interface",
            nav_text_cn="迷失之地配置",
        )

        self.ctx: ZContext = ctx
        self.group_id: str = application_const.DEFAULT_GROUP_ID

    def set_group_id(self, group_id: str) -> None:
        self.group_id = group_id
        
    def get_content_widget(self) -> QWidget:
        # 创建一个容器 widget 用于水平排列
        col_widget = QWidget(self)
        col_layout = QHBoxLayout(col_widget)
        col_widget.setLayout(col_layout)

        # 将左侧和右侧的 widget 添加到主布局中，并均分空间
        col_layout.addWidget(self._get_left_opts(), stretch=1)
        col_layout.addWidget(self._get_right_opts(), stretch=1)

        return col_widget

    def _get_left_opts(self) -> QWidget:
        # 创建左侧的垂直布局容器
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_widget.setLayout(left_layout)

        self.help_opt = HelpCard(url='https://one-dragon.com/zzz/zh/docs/feat_hollow_zero.html')
        left_layout.addWidget(self.help_opt)

        self.mission_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,  # 选择与挑战相关的图标
            title='挑战副本',
            content='选择副本',
        )
        left_layout.addWidget(self.mission_opt)

        self.task_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.CALENDAR,  # 选择与时间相关的图标
            title='刷取目标',
            options_enum=LostVoidTaskEnum
        )
        self.task_type_opt.value_changed.connect(self._update_run_record_display)
        left_layout.addWidget(self.task_type_opt)

        self.weekly_plan_times_opt = SpinBoxSettingCard(
            icon=FluentIcon.CALENDAR,  # 选择与时间相关的图标
            title='每周进入次数',
        )
        self.weekly_plan_times_opt.setVisible(False)
        left_layout.addWidget(self.weekly_plan_times_opt)

        left_layout.addStretch(1)
        return left_widget

    def _get_right_opts(self) -> QWidget:
        # 创建右侧的垂直布局容器
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_widget.setLayout(right_layout)

        self.run_record_opt = PushSettingCard(
            icon=FluentIcon.SYNC,
            title='运行记录',
            text='重置记录'
        )
        self.run_record_opt.clicked.connect(self._on_reset_record_clicked)
        right_layout.addWidget(self.run_record_opt)

        self.challenge_config_opt = ComboBoxSettingCard(
            icon=FluentIcon.SETTING,  # 选择与设置相关的图标
            title='挑战配置', content='选择角色、鸣徽和事件',
        )
        right_layout.addWidget(self.challenge_config_opt)

        self.daily_plan_times_opt = SpinBoxSettingCard(
            icon=FluentIcon.CALENDAR,
            title='每天进入次数',
            content='分摊到每天运行',
        )
        right_layout.addWidget(self.daily_plan_times_opt)

        right_layout.addStretch(1)
        return right_widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        super().on_interface_shown()
        self.config: LostVoidConfig = self.ctx.run_context.get_config(
            app_id=lost_void_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.run_record: LostVoidRunRecord = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=lost_void_const.APP_ID,
        )

        self._update_mission_options()
        self._update_challenge_config_options()
        self.challenge_config_opt.init_with_adapter(get_prop_adapter(self.config, 'challenge_config'))

        self.mission_opt.init_with_adapter(get_prop_adapter(self.config, 'mission_name'))
        self._update_run_record_display()

        self.daily_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, 'daily_plan_times'))
        self.task_type_opt.init_with_adapter(get_prop_adapter(self.config, 'extra_task'))
        self.weekly_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, 'weekly_plan_times'))

    def _update_run_record_display(self) -> None:
        if self.run_record.bounty_commission_complete:
            content = '已完成悬赏委托 如错误可重置'
        elif self.run_record.period_reward_complete:
            content = '已完成刷取周期奖励 如错误可重置'
        elif self.run_record.eval_point_complete:
            content = '已完成刷取业绩 如错误可重置'
        else:
            content = '通关次数 本日: %d, 本周: %d' % (self.run_record.daily_run_times, self.run_record.weekly_run_times)
        self.run_record_opt.setContent(content)
        self.weekly_plan_times_opt.setVisible(self.config.extra_task == LostVoidTaskEnum.WEEKLY_PLAN_TIMES.value.value)

    def _update_mission_options(self) -> None:
        self.mission_opt.blockSignals(True)
        mission_list: list[str] = self.ctx.compendium_service.get_lost_void_mission_name_list()
        opt_list = [
            ConfigItem(mission_name)
            for mission_name in mission_list
        ]
        self.mission_opt.set_options_by_list(opt_list)
        self.mission_opt.blockSignals(False)

    def _update_challenge_config_options(self) -> None:
        """
        更新已有的yml选项
        :return:
        """
        config_list: list[LostVoidChallengeConfig] = get_all_lost_void_challenge_config()
        opt_list = [
            ConfigItem(config.module_name, config.module_name)
            for config in config_list
        ]
        self.challenge_config_opt.set_options_by_list(opt_list)

    def _on_reset_record_clicked(self) -> None:
        self.run_record.reset_record()
        self.run_record.reset_for_weekly()
        log.info('重置成功')
        self._update_run_record_display()
