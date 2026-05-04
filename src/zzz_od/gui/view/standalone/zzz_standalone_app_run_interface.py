from __future__ import annotations

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon_qt.view.standalone_app_run_interface import StandaloneRunInterface
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.context.zzz_context import ZContext


class ZStandaloneAppRunInterface(StandaloneRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        StandaloneRunInterface.__init__(
            self,
            ctx=ctx,
            object_name='standalone_app_run_interface',
            nav_text_cn='应用运行',
            nav_icon=FluentIcon.APPLICATION,
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        return HelpCard(
            url='https://one-dragon.com/zzz/zh/feat_standalone_app.html',
            title='应用运行说明',
            content='从应用列表中选择单个功能模块独立运行，无需跑完整的一条龙流程',
        )
