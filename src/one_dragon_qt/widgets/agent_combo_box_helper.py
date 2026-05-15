import os
import json
from typing import List, Optional, Callable

from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIconBase

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from one_dragon.utils.yaml_utils import safe_load
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard


class AgentComboBoxHelper:
    """
    代理人下拉框辅助类，提供统一的代理人选项加载和管理功能
    """

    CACHE_EXPIRY_SECONDS: int = 300

    def __init__(self):
        self._agent_options_cache: List[ConfigItem] | None = None
        self._drive_disk_options_cache: List[ConfigItem] | None = None
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

    def get_agent_options_from_intel(self) -> List[ConfigItem]:
        """从 GameDataService 获取代理人选项"""
        from zzz_od.game_data.game_data_service import GameDataService

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

    def get_drive_disk_options_from_intel(self) -> List[ConfigItem]:
        """从 GameDataService 获取驱动盘套装选项"""
        from zzz_od.game_data.game_data_service import GameDataService

        game_data = GameDataService()
        options = []
        for disk_set in game_data.drive_disk_list:
            set_name = disk_set.get("set_name")
            code = disk_set.get("code")
            if set_name and code:
                options.append(ConfigItem(set_name, code))

        log.info(f"从 GameDataService 加载了 {len(options)} 个驱动盘套装")
        return options

    def fallback_load_agent_options(self) -> List[ConfigItem]:
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

    def fallback_load_drive_disk_options(self) -> List[ConfigItem]:
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

    def create_agent_combo_box(
        self,
        icon: Optional[QIcon | FluentIconBase] = None,
        title: str = "选择代理人",
        content: str = "选择要操作的代理人",
        parent=None
    ) -> ComboBoxSettingCard:
        """
        创建代理人选择下拉框
        :param icon: 图标
        :param title: 标题
        :param content: 内容描述
        :param parent: 父控件
        :return: ComboBoxSettingCard 实例
        """
        from qfluentwidgets import FluentIcon
        if icon is None:
            icon = FluentIcon.PEOPLE

        return ComboBoxSettingCard(
            icon=icon,
            title=title,
            content=content,
            parent=parent
        )

    def create_drive_disk_combo_box(
        self,
        icon: Optional[QIcon | FluentIconBase] = None,
        title: str = "选择驱动盘套装",
        content: str = "选择要筛选的驱动盘套装，留空则不进行筛选",
        parent=None
    ) -> ComboBoxSettingCard:
        """
        创建驱动盘套装选择下拉框
        :param icon: 图标
        :param title: 标题
        :param content: 内容描述
        :param parent: 父控件
        :return: ComboBoxSettingCard 实例
        """
        from qfluentwidgets import FluentIcon
        if icon is None:
            icon = FluentIcon.PALETTE

        return ComboBoxSettingCard(
            icon=icon,
            title=title,
            content=content,
            parent=parent
        )

    def update_agent_options(self, combo_box: ComboBoxSettingCard, use_cache: bool = True) -> None:
        """
        更新代理人下拉框选项
        :param combo_box: ComboBoxSettingCard 实例
        :param use_cache: 是否使用缓存
        """
        options = []

        try:
            if use_cache and self._is_cache_valid() and self._agent_options_cache is not None:
                options = self._agent_options_cache
                log.info("使用缓存的代理人选项")
            else:
                options = self.get_agent_options_from_intel()
                self._agent_options_cache = options
                self._update_cache_timestamp()
        except Exception as e:
            log.error(f"从 GameDataService 获取代理人数据失败: {e}")
            options = self.fallback_load_agent_options()

        combo_box.set_options_by_list(options)

    def update_drive_disk_options(self, combo_box: ComboBoxSettingCard, use_cache: bool = True) -> None:
        """
        更新驱动盘套装下拉框选项
        :param combo_box: ComboBoxSettingCard 实例
        :param use_cache: 是否使用缓存
        """
        options = []

        try:
            if use_cache and self._is_cache_valid() and self._drive_disk_options_cache is not None:
                options = self._drive_disk_options_cache
                log.info("使用缓存的驱动盘套装选项")
            else:
                options = self.get_drive_disk_options_from_intel()
                self._drive_disk_options_cache = options
                self._update_cache_timestamp()
        except Exception as e:
            log.error(f"从 GameDataService 获取驱动盘数据失败: {e}")
            options = self.fallback_load_drive_disk_options()

        combo_box.set_options_by_list(options)

    def load_agent_options_from_scan_file(self) -> List[ConfigItem]:
        """
        从预扫描生成的 agent_names.json 文件加载代理人选项
        :return: ConfigItem 列表
        """
        options = []
        data_file_path = os_utils.get_path_under_work_dir(".debug", "inventory_data")
        agent_names_file_path = os.path.join(data_file_path, "agent_names.json")

        try:
            log.info(f"[DEBUG] agent_names_file_path: {agent_names_file_path}, 是否存在: {os.path.exists(agent_names_file_path)}")
            with open(agent_names_file_path, encoding="utf-8") as f:
                agent_info_list = json.load(f)
                log.info(f"[DEBUG] agent_info_list: {agent_info_list}")

                for agent_info in agent_info_list:
                    code = agent_info.get("code")
                    display_name = agent_info.get("display_name", code)
                    log.info(f"[DEBUG] code={code}, display_name={display_name}")
                    options.append(ConfigItem(display_name, code))
        except FileNotFoundError:
            log.info(f"文件 {agent_names_file_path} 不存在，请先执行预扫描生成代理人列表")
        except json.JSONDecodeError:
            log.error(f"文件 {agent_names_file_path} 格式错误")
        except Exception as e:
            log.error(f"更新代理人选项失败: {e}")

        return options

    def update_agent_options_from_scan(self, combo_box: ComboBoxSettingCard) -> None:
        """
        从预扫描文件更新代理人下拉框选项（用于特定扫描）
        :param combo_box: ComboBoxSettingCard 实例
        """
        options = self.load_agent_options_from_scan_file()
        combo_box.set_options_by_list(options)


# 创建单例实例
agent_combo_box_helper = AgentComboBoxHelper()