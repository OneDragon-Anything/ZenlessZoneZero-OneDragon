import json
import os
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from one_dragon.utils.yaml_utils import safe_load
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.back_to_world import back_to_world_const
from zzz_od.context.zzz_context import ZContext


class BackToWorldInterface(AppRunInterface):
    """返回大世界界面"""

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        
        # 初始化数据文件路径
        self.data_file_path = os_utils.get_path_under_work_dir(
            ".debug", "inventory_data"
        )
        
        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=back_to_world_const.APP_ID,
            object_name="back_to_world_interface",
            nav_text_cn="返回大世界",
            nav_icon=FluentIcon.HOME,
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        """构建顶部内容区域"""
        from one_dragon_qt.widgets.column import Column
        
        top = Column()
        
        help_card = HelpCard(
            title="功能说明",
            content="将游戏从任何状态智能返回到大世界（普通世界），并导航到指定代理人的信息界面。\n\n"
                    "支持的状态包括：\n"
                    "• 菜单界面\n"
                    "• 战斗界面\n"
                    "• 对话界面\n"
                    "• 邮件界面\n"
                    "• 商店界面\n"
                    "• 空洞探索\n"
                    "• 好感度事件\n"
                    "• 快捷手册\n"
                    "• 其他特殊界面\n\n"
                    "使用方法：选择要导航的代理人，然后点击下方的运行按钮即可开始执行。",
        )
        top.add_widget(help_card)
        
        # 代理人选择下拉框
        self.agent_select_opt = ComboBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            title="选择代理人",
            content="选择要导航到的代理人"
        )
        top.add_widget(self.agent_select_opt)
        
        return top
    
    def _update_agent_options(self) -> None:
        """更新代理人选项"""
        agent_names_file_path = os.path.join(self.data_file_path, "agent_names.json")
        options = []
        
        try:
            # 优先读取 agent_names.json
            if os.path.exists(agent_names_file_path):
                log.info(f"从 {agent_names_file_path} 加载代理人列表")
                with open(agent_names_file_path, encoding="utf-8") as f:
                    agent_codes = json.load(f)
                    
                # 从 YAML 文件获取代理人名称映射
                agent_name_dict = {}
                yaml_path = os_utils.get_path_under_work_dir(
                    "assets", "game_data", "agent", "_od_merged.yml"
                )
                if os.path.exists(yaml_path):
                    with open(yaml_path, encoding="utf-8") as f:
                        agents_data = safe_load(f)
                        for agent in agents_data:
                            code = agent.get("code")
                            if code:
                                agent_name_dict[code] = agent.get("agent_name", code)
                
                # 创建选项
                for code in agent_codes:
                    if code in agent_name_dict:
                        chs_name = agent_name_dict[code]
                    else:
                        chs_name = code
                    options.append(ConfigItem(chs_name, code))
            else:
                # 如果 agent_names.json 不存在，则从 YAML 文件读取所有代理人
                log.info(f"{agent_names_file_path} 不存在，从 YAML 文件加载所有代理人")
                yaml_path = os_utils.get_path_under_work_dir(
                    "assets", "game_data", "agent", "_od_merged.yml"
                )
                if os.path.exists(yaml_path):
                    with open(yaml_path, encoding="utf-8") as f:
                        agents_data = safe_load(f)
                        for agent in agents_data:
                            code = agent.get("code")
                            agent_name = agent.get("agent_name", code)
                            if code:
                                options.append(ConfigItem(agent_name, code))
                else:
                    log.warning("YAML 文件也不存在，无法加载代理人列表")
                    
        except FileNotFoundError:
            log.warning(f"文件 {agent_names_file_path} 不存在")
        except json.JSONDecodeError:
            log.error(f"文件 {agent_names_file_path} 格式错误")
        except Exception as e:
            log.error(f"更新代理人选项失败: {e}")
        
        # 更新下拉框选项
        if hasattr(self, "agent_select_opt"):
            self.agent_select_opt.set_options_by_list(options)
    
    def on_interface_shown(self) -> None:
        """在界面显示时调用"""
        super().on_interface_shown()
        # 更新代理人选项
        self._update_agent_options()
    
    def _on_start_clicked(self) -> None:
        """在启动应用前保存用户选择的配置"""
        # 保存选择的代理人代码
        if hasattr(self, "agent_select_opt") and self.agent_select_opt:
            selected_value = self.agent_select_opt.getValue()
            self.ctx._back_to_world_agent_code = selected_value
            log.info(f"返回大世界：选择的代理人: {selected_value}")
        else:
            self.ctx._back_to_world_agent_code = None
            log.info("返回大世界：未选择代理人")
        
        # 调用父类方法启动应用
        AppRunInterface._on_start_clicked(self)
