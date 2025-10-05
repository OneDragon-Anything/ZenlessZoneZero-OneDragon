from typing import Optional

from one_dragon_qt.view.app_run_interface import AppRunInterface
from zzz_od.application.game_config_checker import mouse_sensitivity_checker_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class MouseSensitivityCheckerInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=mouse_sensitivity_checker_const.APP_ID,
            object_name='mouse_sensitivity_checker_interface',
            nav_text_cn='鼠标校准',
            parent=parent,
        )

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)
