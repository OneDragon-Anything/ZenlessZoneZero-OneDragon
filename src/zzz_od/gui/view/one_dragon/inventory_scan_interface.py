import json
import os
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon
from one_dragon.utils import os_utils
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.inventory_scan import inventory_scan_const
from zzz_od.application.inventory_scan.inventory_scan_config import AgentScanOptionEnum
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from one_dragon.base.config.config_item import ConfigItem


class InventoryScanInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: ZApplication | None = None
        #初始化数据文件路径
        self.data_file_path = os_utils.get_path_under_work_dir('.debug', 'inventory_data')

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=inventory_scan_const.APP_ID,
            object_name='inventory_scan_interface',
            nav_text_cn='仓库扫描',
            parent=parent,
        )

    def on_interface_shown(self)->None:
        """在界面显示时调用"""
        super().on_interface_shown()
        agent_names_file_path = os.path.join(self.data_file_path, 'agent_names.json')
        # 从枚举创建初始选项
        options = [item.value for item in AgentScanOptionEnum]
        try:
            # 读取文件并添加代理人选项
            with open(agent_names_file_path, 'r', encoding='utf-8') as f:
                agent_names = json.load(f)
                for name in agent_names:
                   options.append(ConfigItem(name))
        except FileNotFoundError:
            print(f"文件 {agent_names_file_path} 不存在，将使用默认选项{options}")
        except json.JSONDecodeError:
            print(f"文件 {agent_names_file_path} 格式错误，将使用默认选项{options}")
        except Exception as e:
            print(f"读取文件 {agent_names_file_path} 时发生错误: {e}，将使用默认选项{options}")
        # 更新下拉框选项
        self.scan_agent_opt.set_options_by_list(options)
    
    def get_widget_at_top(self) -> QWidget:

        content = Row()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        content.h_layout.addLayout(left_layout)
        content.h_layout.addLayout(right_layout)
        self.help_opt = HelpCard(
            title='使用说明',
            content='点击「开始」后将自动扫描仓库中的物品信息'
        )
        left_layout.addWidget(self.help_opt)
        self.scan_agent_opt =ComboBoxSettingCard(
            icon=FluentIcon.SEARCH,
            title='特定代理人扫描'
        )
        left_layout.addWidget(self.scan_agent_opt)
        return content
    
    def _on_start_clicked(self) -> None:
        """在启动应用前保存用户选择的配置"""
        #将scan_agent_opt的值保存到context
        if hasattr(self, 'scan_agent_opt') and self.scan_agent_opt:
            selected_value = self.scan_agent_opt.getValue()
            # 将选择的值存储到 context 中
            setattr(self.ctx, '_inventory_scan_agent_option', selected_value)
            print(f"选择的代理人扫描选项: {selected_value}")
        # 调用父类方法启动应用
        AppRunInterface._on_start_clicked(self)