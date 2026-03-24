from PySide6.QtWidgets import QWidget

from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.inventory_scan import inventory_scan_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class InventoryScanInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: ZApplication | None = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=inventory_scan_const.APP_ID,
            object_name='inventory_scan_interface',
            nav_text_cn='仓库扫描',
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        return HelpCard(
            title='使用说明',
            content='点击「开始」后将自动扫描仓库中的物品信息'
        )