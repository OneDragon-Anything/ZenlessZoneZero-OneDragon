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
            nav_text_cn='搴旂敤杩愯',
            nav_icon=FluentIcon.APPLICATION,
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        help_base_url = self.ctx.project_config.home_page_link.rsplit('/', 1)[0]
        return HelpCard(
            url=f'{help_base_url}/feat_standalone_app.html',
            title='搴旂敤杩愯璇存槑',
            content='浠庝竴鏉￠緳杩愯鍒楄〃涓嚜鐢辨坊鍔犲簲鐢紝鎵嬪姩閫夋嫨鍗曚釜鍔熻兘鎸夐渶杩愯',
        )
