from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, PushSettingCard

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.hollow_zero.hollow_period_speed import hollow_period_speed_const
from zzz_od.application.hollow_zero.hollow_period_speed.hollow_period_speed_config import (
    HollowPeriodSpeedGoal,
)
from zzz_od.game_data.agent import AgentEnum, AgentTypeEnum

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class HollowPeriodSpeedSettingInterface(VerticalScrollInterface, GroupIdMixin):

    def __init__(self, ctx: ZContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='hollow_period_speed_setting_interface',
            nav_text_cn='空洞周期速刷配置',
            parent=parent,
        )

        self.ctx: ZContext = ctx

    def get_content_widget(self) -> QWidget:
        widget = Column()

        self.goal_opt = ComboBoxSettingCard(
            icon=FluentIcon.CALENDAR,
            title='刷取目标',
            content='刷满零号业绩，或刷满丁尼',
            options_enum=HollowPeriodSpeedGoal,
        )
        widget.add_widget(self.goal_opt)

        self.agent_btn_list: list[EditableComboBox] = []
        for _ in range(3):
            agent_btn = EditableComboBox()
            agent_btn.currentIndexChanged.connect(self._on_agent_changed)
            self.agent_btn_list.append(agent_btn)
        self.agents_opt = MultiPushSettingCard(
            btn_list=self.agent_btn_list, icon=FluentIcon.PEOPLE,
            title='目标配队', content='按照自动战斗配置 选择角色位置',
        )
        widget.add_widget(self.agents_opt)

        self.auto_battle_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='自动战斗', content='战斗使用的自动战斗配置',
        )
        widget.add_widget(self.auto_battle_opt)

        self.daily_plan_times_opt = SpinBoxSettingCard(
            icon=FluentIcon.CALENDAR,
            title='每天进入次数',
            content='将空洞分摊到每天运行',
        )
        widget.add_widget(self.daily_plan_times_opt)

        self.run_record_opt = PushSettingCard(
            icon=FluentIcon.SYNC,
            title='运行记录',
            text='重置记录'
        )
        self.run_record_opt.clicked.connect(self._on_reset_record_clicked)
        widget.add_widget(self.run_record_opt)

        widget.add_stretch(1)
        return widget

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        super().on_interface_shown()

        self.config = self.ctx.run_context.get_config(
            app_id=hollow_period_speed_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.run_record = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=hollow_period_speed_const.APP_ID,
        )

        self.goal_opt.init_with_adapter(get_prop_adapter(self.config, 'goal'))
        self._update_agent_options()
        self.auto_battle_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))
        self.auto_battle_opt.init_with_adapter(get_prop_adapter(self.config, 'auto_battle'))
        self.daily_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, 'daily_plan_times'))
        self._update_run_record_display()

    def _update_agent_options(self) -> None:
        agent_opts = [
            ConfigItem(agent_type_enum.value)
            for agent_type_enum in AgentTypeEnum
            if agent_type_enum.value != '未知'
        ] + [
            ConfigItem(label=agent_enum.value.agent_name, value=agent_enum.value.agent_id)
            for agent_enum in AgentEnum
        ]
        agents = self.config.target_agents
        for i in range(3):
            btn = self.agent_btn_list[i]
            btn.blockSignals(True)
            btn.set_items(agent_opts, agents[i] if i < len(agents) else None)
            btn.blockSignals(False)

    def _on_agent_changed(self, idx: int) -> None:
        agents: list[str | None] = []
        for btn in self.agent_btn_list:
            agents.append(None if btn.currentIndex() == -1 else btn.currentData())
        self.config.target_agents = agents

    def _update_run_record_display(self) -> None:
        if self.run_record.is_finished_by_week():
            content = '已完成本周刷取目标 如错误可重置'
        else:
            content = f'进入次数 本日: {self.run_record.daily_run_times}'
        self.run_record_opt.setContent(content)

    def _on_reset_record_clicked(self) -> None:
        self.run_record.reset_for_weekly()
        log.info('重置成功')
        self._update_run_record_display()
