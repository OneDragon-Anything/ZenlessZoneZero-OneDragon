from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
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
            nav_text_cn='插件中心',
            nav_icon=FluentIcon.APPLICATION,
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(HelpCard(
            url='https://one-dragon.com/zzz/zh/feat/feat_standalone_app.html',
            title='应用运行说明',
            content='从应用列表中选择单个功能模块独立运行，无需跑完整的一条龙流程',
        ))
        layout.addWidget(HelpCard(
            url='https://zzz-optimizer.neko11.workers.dev/',
            text='红豆站',
            title='插件商城 — 红豆站',
            content='浏览和下载第三方插件',
        ))
        layout.addWidget(HelpCard(
            url='https://zzz-opt-1.a-7-s.club/',
            text='葱站',
            title='插件商城 — 葱站',
            content='浏览和下载第三方插件',
        ))

        return top
