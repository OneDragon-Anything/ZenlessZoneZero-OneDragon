from PySide6.QtWidgets import QWidget

from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.game_config_checker.mouse_sensitivity_checker import (
    mouse_sensitivity_checker_const,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class MouseSensitivityCheckerInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: ZApplication | None = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=mouse_sensitivity_checker_const.APP_ID,
            object_name='mouse_sensitivity_checker_interface',
            nav_text_cn='灵敏度校准',
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        return HelpCard(
            title='使用说明',
            content='点击「开始」后将自动校准鼠标/手柄的转向灵敏度，用于视角转动'
        )
