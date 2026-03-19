from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from one_dragon_qt.widgets.setting_card.app_run_card import AppRunCard
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanInterface
from zzz_od.gui.view.one_dragon.mouse_sensitivity_checker_interface import MouseSensitivityCheckerInterface
from zzz_od.gui.view.one_dragon.predefined_team_interface import PredefinedTeamInterface
from zzz_od.gui.view.one_dragon.zzz_one_dragon_run_interface import ZOneDragonRunInterface


class ZOneDragonInterface(PivotNavigatorInterface):

    def __init__(self, ctx: ZContext, parent=None) -> None:
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(
            self,
            nav_icon=FluentIcon.BUS,
            object_name='one_dragon_interface',
            parent=parent,
            nav_text_cn='一条龙'
        )

        self._app_run_cards: list[AppRunCard] = []

    def create_sub_interface(self) -> None:
        self.add_sub_interface(ZOneDragonRunInterface(self.ctx))
        self.add_sub_interface(ChargePlanInterface(self.ctx))
        self.add_sub_interface(PredefinedTeamInterface(self.ctx))
        self.add_sub_interface(MouseSensitivityCheckerInterface(self.ctx))

    def on_interface_shown(self) -> None:
        if self.ctx.signal.start_onedragon:
            self.stacked_widget.setCurrentIndex(0)
        super().on_interface_shown()
