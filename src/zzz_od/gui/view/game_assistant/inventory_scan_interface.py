import os
import webbrowser
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QVBoxLayout, QWidget, QLabel
from qfluentwidgets import FluentIcon, PushButton, CheckBox

from one_dragon.base.operation.application import application_const
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
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
        # 扫描目标选择
        self.scan_drive_disk_check: Optional[CheckBox] = None
        self.scan_wengine_check: Optional[CheckBox] = None
        self.scan_agent_check: Optional[CheckBox] = None

    def get_widget_at_top(self) -> QWidget:
        content = Row()
        left_layout = QVBoxLayout()
        content.h_layout.addLayout(left_layout)

        # 使用说明卡片
        self.help_opt = HelpCard(
            title='使用说明',
            content='从大世界开始，自动扫描驱动盘、音擎、角色，并导出数据。扫描结果可导入绝区零伤害优化计算网站进行配装分析。'
        )
        left_layout.addWidget(self.help_opt)

        # 链接按钮行
        from one_dragon_qt.widgets.row import Row as HRow
        link_row = HRow()

        self.open_output_btn = PushButton('打开输出目录', link_row, FluentIcon.FOLDER)
        self.open_output_btn.clicked.connect(self._on_open_output_clicked)
        link_row.h_layout.addWidget(self.open_output_btn)

        self.open_error_btn = PushButton('打开错误目录', link_row, FluentIcon.FOLDER_ADD)
        self.open_error_btn.clicked.connect(self._on_open_error_clicked)
        link_row.h_layout.addWidget(self.open_error_btn)

        self.github_btn = PushButton('问题反馈', link_row, FluentIcon.GITHUB)
        self.github_btn.clicked.connect(self._on_github_clicked)
        link_row.h_layout.addWidget(self.github_btn)

        self.analyze_btn = PushButton('分析网站', link_row, FluentIcon.LINK)
        self.analyze_btn.clicked.connect(self._on_analyze_clicked)
        link_row.h_layout.addWidget(self.analyze_btn)

        left_layout.addWidget(link_row)

        # 扫描目标选择
        from qfluentwidgets import BodyLabel

        scan_target_row = HRow()
        scan_target_label = BodyLabel('扫描内容：', scan_target_row)
        scan_target_row.h_layout.addWidget(scan_target_label)

        self.scan_drive_disk_check = CheckBox('驱动盘', scan_target_row)
        self.scan_drive_disk_check.setChecked(True)
        scan_target_row.h_layout.addWidget(self.scan_drive_disk_check)

        self.scan_wengine_check = CheckBox('音擎', scan_target_row)
        self.scan_wengine_check.setChecked(True)
        scan_target_row.h_layout.addWidget(self.scan_wengine_check)

        self.scan_agent_check = CheckBox('角色', scan_target_row)
        self.scan_agent_check.setChecked(True)
        scan_target_row.h_layout.addWidget(self.scan_agent_check)

        left_layout.addWidget(scan_target_row)

        return content

    def _on_open_output_clicked(self):
        """打开输出目录按钮点击事件"""
        output_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_exports')
        os.startfile(output_dir)

    def _on_open_error_clicked(self):
        """打开错误目录按钮点击事件"""
        error_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_errors')
        os.makedirs(error_dir, exist_ok=True)
        os.startfile(error_dir)

    def _on_github_clicked(self):
        """打开 GitHub 链接（问题反馈）"""
        github_url = 'https://github.com/kawayiYokami/zzz_optimizer'
        QDesktopServices.openUrl(QUrl(github_url))

    def _on_analyze_clicked(self):
        """打开分析网站"""
        webbrowser.open('https://zzzop.netlify.app/')

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)
        self.config = self.ctx.run_context.get_config(
            app_id=inventory_scan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

    def _on_start_clicked(self) -> None:
        """在启动应用前保存扫描目标配置"""
        # 保存扫描目标选择到 context
        if hasattr(self, 'scan_drive_disk_check') and self.scan_drive_disk_check:
            targets = {
                'drive_disk': self.scan_drive_disk_check.isChecked(),
                'wengine': self.scan_wengine_check.isChecked(),
                'agent': self.scan_agent_check.isChecked(),
            }
            setattr(self.ctx, '_inventory_scan_targets', targets)
            log.info(f"扫描目标: {targets}")
        
        # 调用父类方法启动应用
        AppRunInterface._on_start_clicked(self)

    def on_interface_hidden(self) -> None:
        AppRunInterface.on_interface_hidden(self)
