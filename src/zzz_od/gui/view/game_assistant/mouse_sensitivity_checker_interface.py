from typing import Optional

from one_dragon.base.operation.application_base import Application
from one_dragon_qt.view.app_run_interface import AppRunInterface
from zzz_od.application.game_config_checker.mouse_sensitivity_checker import MouseSensitivityChecker
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
            object_name='mouse_sensitivity_checker_interface',
            nav_text_cn='鼠标校准',
            parent=parent,
        )

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)

    def get_app(self) -> Application:
        return MouseSensitivityChecker(self.ctx)
