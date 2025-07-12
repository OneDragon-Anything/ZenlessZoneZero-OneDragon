from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon
from typing import Optional

from one_dragon.base.operation.application_base import Application
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.predefined_team_checker.predefined_team_checker import PredefinedTeamChecker
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class PredefinedTeamCheckerInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            object_name='predefined_team_checker_interface',
            nav_text_cn='预备编队识别',
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        content = Column()

        self.help_opt = HelpCard(title='一条龙-预备编队中输入正确编队名称后运行',
                                 content='根据队伍名称识别对应的代理人')
        content.add_widget(self.help_opt)

        return content

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)

    def get_app(self) -> Application:
        return PredefinedTeamChecker(self.ctx)
