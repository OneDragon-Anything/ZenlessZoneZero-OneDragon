from __future__ import annotations

from qfluentwidgets import FluentIcon

from one_dragon_qt.view.standalone_app_run_interface import StandaloneRunInterface
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
