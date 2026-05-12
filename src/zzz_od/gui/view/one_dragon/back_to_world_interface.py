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
from zzz_od.game_data.game_data_service import GameDataService


class BackToWorldInterface(AppRunInterface):
    """返回大世界界面"""

    CACHE_EXPIRY_SECONDS: int = 300

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=back_to_world_const.APP_ID,
            object_name="back_to_world_interface",
            nav_text_cn="返回大世界",
            nav_icon=FluentIcon.HOME,
            parent=parent,
        )

        self._agent_options_cache: list[ConfigItem] | None = None
        self._drive_disk_options_cache: list[ConfigItem] | None = None
        self._options_cache_timestamp: float = 0.0

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        import time
        if self._agent_options_cache is None or self._drive_disk_options_cache is None:
            return False
        return (time.time() - self._options_cache_timestamp) < self.CACHE_EXPIRY_SECONDS

    def _update_cache_timestamp(self) -> None:
        """更新缓存时间戳"""
        import time
        self._options_cache_timestamp = time.time()

    def _get_agent_options_from_intel(self) -> list[ConfigItem]:
        """从 GameDataService 获取代理人选项"""

        game_data = GameDataService()

        scanned_codes = game_data.scanned_agent_codes

        if scanned_codes:
            log.info(f"从 GameDataService 加载已扫描代理人列表")
            options = []
            agent_map = {agent.get("code"): agent for agent in game_data.agent_list if agent.get("code")}
            for code in scanned_codes:
                if code in agent_map:
                    agent = agent_map[code]
                    options.append(ConfigItem(agent.get("agent_name", code), code))
                else:
                    log.warning(f"agent_names.json 中的代码 {code} 在 GameDataService 中未找到")
            log.info(f"从已扫描列表加载了 {len(options)} 个代理人")
        else:
            options = []
            for agent in game_data.agent_list:
                code = agent.get("code")
                agent_name = agent.get("agent_name", code)
                if code:
                    options.append(ConfigItem(agent_name, code))
            log.info(f"从 GameDataService 加载了全部 {len(options)} 个代理人")

        return options

    def _get_drive_disk_options_from_intel(self) -> list[ConfigItem]:
        """从 GameDataService 获取驱动盘套装选项"""

        game_data = GameDataService()

        options = []
        for disk_set in game_data.drive_disk_list:
            set_name = disk_set.get("set_name")
            code = disk_set.get("code")
            if set_name and code:
                options.append(ConfigItem(set_name, code))

        log.info(f"从 GameDataService 加载了 {len(options)} 个驱动盘套装")
        return options

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

        # 驱动盘套装选择下拉框
        self.drive_disk_set_opt = ComboBoxSettingCard(
            icon=FluentIcon.PALETTE,
            title="选择驱动盘套装（可选）",
            content="选择要筛选的驱动盘套装，留空则不进行筛选"
        )
        top.add_widget(self.drive_disk_set_opt)

        return top

    def _update_agent_options(self) -> None:
        """更新代理人选项"""
        options = []

        try:
            if self._is_cache_valid() and self._agent_options_cache is not None:
                options = self._agent_options_cache
                log.info("使用缓存的代理人选项")
            else:
                options = self._get_agent_options_from_intel()
                self._agent_options_cache = options
                self._update_cache_timestamp()
        except Exception as e:
            log.error(f"从 GameDataService 获取代理人数据失败: {e}")
            options = self._fallback_load_agent_options()

        if hasattr(self, "agent_select_opt"):
            self.agent_select_opt.set_options_by_list(options)

    def _update_drive_disk_set_options(self) -> None:
        """更新驱动盘套装选项"""
        options = []

        try:
            if self._is_cache_valid() and self._drive_disk_options_cache is not None:
                options = self._drive_disk_options_cache
                log.info("使用缓存的驱动盘套装选项")
            else:
                options = self._get_drive_disk_options_from_intel()
                self._drive_disk_options_cache = options
                self._update_cache_timestamp()
        except Exception as e:
            log.error(f"从 GameDataService 获取驱动盘数据失败: {e}")
            options = self._fallback_load_drive_disk_options()

        if hasattr(self, "drive_disk_set_opt"):
            self.drive_disk_set_opt.set_options_by_list(options)

    def _fallback_load_agent_options(self) -> list[ConfigItem]:
        """回退方法：从文件加载代理人选项（当 GameDataService 不可用时）"""
        options = []
        try:
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
                log.info(f"从回退文件加载了 {len(options)} 个代理人")
        except Exception as e:
            log.error(f"回退加载代理人选项失败: {e}")

        return options

    def _fallback_load_drive_disk_options(self) -> list[ConfigItem]:
        """回退方法：从文件加载驱动盘套装选项（当 GameDataService 不可用时）"""
        options = []
        try:
            yaml_path = os_utils.get_path_under_work_dir(
                "assets", "game_data", "drive_disk", "_od_merged.yml"
            )
            if os.path.exists(yaml_path):
                with open(yaml_path, encoding="utf-8") as f:
                    drive_disk_data = safe_load(f)
                    for item in drive_disk_data:
                        set_name = item.get("set_name")
                        code = item.get("code")
                        if set_name and code:
                            options.append(ConfigItem(set_name, code))
                log.info(f"从回退文件加载了 {len(options)} 个驱动盘套装")
        except Exception as e:
            log.error(f"回退加载驱动盘套装选项失败: {e}")

        return options

    def on_interface_shown(self) -> None:
        """在界面显示时调用"""
        super().on_interface_shown()
        # 更新代理人选项和驱动盘套装选项
        self._update_agent_options()
        self._update_drive_disk_set_options()

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

        # 保存选择的驱动盘套装
        if hasattr(self, "drive_disk_set_opt") and self.drive_disk_set_opt:
            selected_set = self.drive_disk_set_opt.getValue()
            self.ctx._back_to_world_drive_disk_set = selected_set
            log.info(f"返回大世界：选择的驱动盘套装: {selected_set}")
        else:
            self.ctx._back_to_world_drive_disk_set = None
            log.info("返回大世界：未选择驱动盘套装")

        # 调用父类方法启动应用
        AppRunInterface._on_start_clicked(self)
