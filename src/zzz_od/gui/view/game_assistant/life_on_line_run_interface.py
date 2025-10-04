from typing import Optional

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application import application_const
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from zzz_od.application.life_on_line import life_on_line_const
from zzz_od.application.life_on_line.life_on_line_config import LifeOnLineConfig
from zzz_od.application.life_on_line.life_on_line_run_record import LifeOnLineRunRecord
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class LifeOnLineRunInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=life_on_line_const.APP_ID,
            object_name='life_on_line_run_interface',
            nav_text_cn='拿命验收',
            parent=parent,
        )
        self.config: Optional[LifeOnLineConfig] = None
        self.run_record: Optional[LifeOnLineRunRecord] = None

    def get_widget_at_top(self) -> QWidget:
        content = Column()

        self.help_opt = HelpCard(url='https://one-dragon.com/zzz/zh/docs/feat_game_assistant.html#_2-%E6%8B%BF%E5%91%BD%E9%AA%8C%E6%94%B6')
        content.add_widget(self.help_opt)

        self.daily_plan_times_opt = SpinBoxSettingCard(icon=FluentIcon.CALENDAR, title='每日次数', maximum=20000, min_width=150)
        content.add_widget(self.daily_plan_times_opt)

        self.team_opt = ComboBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            title='预备编队',
        )
        content.add_widget(self.team_opt)

        return content

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)

        self.config: Optional[LifeOnLineConfig] = self.ctx.run_context.get_config(
            app_id=life_on_line_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: Optional[LifeOnLineRunRecord] = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=life_on_line_const.APP_ID,
        )

        self.daily_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, 'daily_plan_times'))
        self.daily_plan_times_opt.setContent('完成次数 当日: %d' % self.run_record.daily_run_times)

        config_list = ([ConfigItem('游戏内配队', -1)] +
                       [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.team_opt.set_options_by_list(config_list)
        self.team_opt.init_with_adapter(get_prop_adapter(self.config, 'predefined_team_idx'))
