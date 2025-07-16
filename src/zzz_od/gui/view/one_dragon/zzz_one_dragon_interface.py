from qfluentwidgets import FluentIcon
from typing import List

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from one_dragon_qt.widgets.setting_card.app_run_card import AppRunCard
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanInterface
from zzz_od.gui.view.one_dragon.coffee_plan_interface import CoffeePlanInterface
from zzz_od.gui.view.one_dragon.notorious_hunt_interface import NotoriousHuntPlanInterface
from zzz_od.gui.view.one_dragon.setting_team_interface import SettingTeamInterface
from zzz_od.gui.view.one_dragon.shiyu_defense_interface import ShiyuDefenseInterface
from zzz_od.gui.view.one_dragon.zzz_one_dragon_run_interface import ZOneDragonRunInterface
from zzz_od.gui.view.one_dragon.zzz_one_dragon_setting_interface import ZOneDragonSettingInterface


class ZOneDragonInterface(PivotNavigatorInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(
            self,
            nav_icon=FluentIcon.BUS,
            object_name='one_dragon_interface',
            parent=parent,
            nav_text_cn='一条龙'
        )

        self._app_run_cards: List[AppRunCard] = []

    def create_sub_interface(self):
        self.add_sub_interface(ZOneDragonRunInterface(self.ctx))
        self.add_sub_interface(SettingTeamInterface(self.ctx))
        self.add_sub_interface(ChargePlanInterface(self.ctx))
        self.add_sub_interface(NotoriousHuntPlanInterface(self.ctx))
        self.add_sub_interface(CoffeePlanInterface(self.ctx))
        self.add_sub_interface(ShiyuDefenseInterface(self.ctx))
        # self.add_sub_interface(MiscellanyRunInterface(self.ctx))
        self.add_sub_interface(ZOneDragonSettingInterface(self.ctx))

    def on_interface_shown(self):
        super().on_interface_shown()
        if self.ctx.signal.start_onedragon:
            self.stacked_widget.setCurrentIndex(0)
