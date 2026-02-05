import os
from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PushButton

from one_dragon.base.operation.application import application_const
from one_dragon.utils import os_utils
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.inventory_scan import inventory_scan_const
from zzz_od.application.inventory_scan.inventory_scan_config import InventoryScanConfig
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class InventoryScanInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=inventory_scan_const.APP_ID,
            object_name='inventory_scan_interface',
            nav_text_cn='仓库自动扫描',
            parent=parent,
        )
        self.config: Optional[InventoryScanConfig] = None

    def get_widget_at_top(self) -> QWidget:
        content = Row()
        left_layout = QVBoxLayout()
        content.h_layout.addLayout(left_layout)

        # 使用说明卡片
        self.help_opt = HelpCard(
            url='https://one-dragon.com/zzz/zh/docs/feat_game_assistant.html',
            title='使用说明',
            content='从大世界开始，自动扫描驱动盘、音擎、角色，并导出数据到 .debug\\inventory_exports 目录'
        )
        left_layout.addWidget(self.help_opt)

        # 打开输出目录按钮
        self.open_output_btn = PushButton('打开输出目录', self, FluentIcon.FOLDER)
        self.open_output_btn.clicked.connect(self._on_open_output_clicked)
        left_layout.addWidget(self.open_output_btn)

        return content

    def _on_open_output_clicked(self):
        """打开输出目录按钮点击事件"""
        output_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_exports')
        os.startfile(output_dir)

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)
        self.config = self.ctx.run_context.get_config(
            app_id=inventory_scan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

    def on_interface_hidden(self) -> None:
        AppRunInterface.on_interface_hidden(self)
