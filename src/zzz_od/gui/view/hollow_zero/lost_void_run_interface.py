from typing import List, Optional

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
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.lost_void.lost_void_app import LostVoidApp
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidChallengeConfig,
    get_all_lost_void_challenge_config,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_config import (
    LostVoidConfig,
    LostVoidExtraTask,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_run_record import (
    LostVoidRunRecord,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class LostVoidRunInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=lost_void_const.APP_ID,
            object_name='lost_void_run_interface',
            nav_text_cn='迷失之地',
            parent=parent,
        )

        self.config: Optional[LostVoidConfig] = None
        self.run_record: Optional[LostVoidRunRecord] = None

    def get_widget_at_top(self) -> QWidget:
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

        self.weekly_plan_times_opt = SpinBoxSettingCard(
            icon=FluentIcon.CALENDAR,  # 选择与时间相关的图标
            title='每周基础次数',
            content='用于完成悬赏委托'
        )
        left_layout.addWidget(self.weekly_plan_times_opt)

        self.extra_task_opt = ComboBoxSettingCard(
            icon=FluentIcon.CALENDAR,  # 选择与时间相关的图标
            title='额外刷取',
            content='完成基础次数后，继续刷取',
            options_enum=LostVoidExtraTask
        )
        left_layout.addWidget(self.extra_task_opt)

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
        AppRunInterface.on_interface_shown(self)
        self.config: Optional[LostVoidConfig] = self.ctx.run_context.get_config(
            app_id=lost_void_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: Optional[LostVoidRunRecord] = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=lost_void_const.APP_ID,
        )
        
        self._update_mission_options()
        self._update_challenge_config_options()
        self.challenge_config_opt.init_with_adapter(get_prop_adapter(self.config, 'challenge_config'))

        self.mission_opt.init_with_adapter(get_prop_adapter(self.config, 'mission_name'))
        self._update_run_record_display()

        self.weekly_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, 'weekly_plan_times'))
        self.daily_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, 'daily_plan_times'))
        self.extra_task_opt.init_with_adapter(get_prop_adapter(self.config, 'extra_task'))

    def _update_run_record_display(self) -> None:
        if self.run_record.period_reward_complete:
            content = '已完成刷取周期性奖励 如错误可重置'
        elif self.run_record.eval_point_complete:
            content = '已完成刷取业绩 如错误可重置'
        else:
            content = '通关次数 本日: %d, 本周: %d' % (self.run_record.daily_run_times, self.run_record.weekly_run_times)
        self.run_record_opt.setContent(content)

    def _update_mission_options(self) -> None:
        self.mission_opt.blockSignals(True)
        mission_list: List[str] = self.ctx.compendium_service.get_lost_void_mission_name_list()
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
        config_list: List[LostVoidChallengeConfig] = get_all_lost_void_challenge_config()
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

    def _on_start_clicked(self) -> None:
        """
        正常运行
        """
        self.app = LostVoidApp(self.ctx)
        AppRunInterface._on_start_clicked(self)

    def _on_context_state_changed(self) -> None:
        """
        按运行状态更新显示
        :return:
        """
        AppRunInterface.on_context_state_changed(self)
        self._update_run_record_display()
