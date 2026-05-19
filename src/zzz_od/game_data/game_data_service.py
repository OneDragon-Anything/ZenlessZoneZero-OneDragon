import json
import os
from typing import Any, Optional
from typing import Dict, List

from one_dragon.base.config.yaml_data_set_loader import YamlDataSetLoader
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class GameDataService:
    """
    游戏数据统一访问服务（单例模式）
    
    核心功能：
    - 统一管理代理人、驱动盘、音擎数据的加载与访问
    - 提供已扫描代理人列表的访问
    - 缓存机制减少 IO 操作
    """

    _instance: Optional['GameDataService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        """初始化数据加载器"""
        self.agent_loader: YamlDataSetLoader[Dict] = self._create_agent_loader()
        self.drive_disk_loader: YamlDataSetLoader[Dict] = self._create_drive_disk_loader()
        self.engine_weapon_loader: YamlDataSetLoader[Dict] = self._create_engine_weapon_loader()

        # 立即加载数据
        self.agent_loader.load()
        self.drive_disk_loader.load()
        self.engine_weapon_loader.load()

        # 缓存
        self._scanned_agent_codes_cache: Optional[List[str]] = None
        self._scanned_agent_codes_timestamp: float = 0.0
        self._scanned_agent_codes_cache_ttl: float = 60.0  # 60秒缓存

    def reload_all(self) -> None:
        """重新加载所有数据"""
        self.agent_loader.load()
        self.drive_disk_loader.load()
        self.engine_weapon_loader.load()
        self._scanned_agent_codes_cache = None

    @property
    def agent_list(self) -> List[Dict]:
        """获取所有代理人列表"""
        return self.agent_loader.data_list

    @property
    def agent_map(self) -> Dict[str, Dict]:
        """获取代理人 code -> 数据 映射"""
        return self.agent_loader.data_map

    @property
    def drive_disk_list(self) -> List[Dict]:
        """获取所有驱动盘套装列表"""
        return self.drive_disk_loader.data_list

    @property
    def drive_disk_map(self) -> Dict[str, Dict]:
        """获取驱动盘 code -> 数据 映射"""
        return self.drive_disk_loader.data_map

    @property
    def engine_weapon_list(self) -> List[Dict]:
        """获取所有音擎列表"""
        return self.engine_weapon_loader.data_list

    @property
    def engine_weapon_map(self) -> Dict[str, Dict]:
        """获取音擎 code -> 数据 映射"""
        return self.engine_weapon_loader.data_map

    @property
    def scanned_agent_codes(self) -> List[str]:
        """获取已扫描的代理人代码列表（带缓存）"""
        import time

        now = time.time()
        if (
            self._scanned_agent_codes_cache is not None
            and (now - self._scanned_agent_codes_timestamp) < self._scanned_agent_codes_cache_ttl
        ):
            return self._scanned_agent_codes_cache

        path = os.path.join(
            os_utils.get_path_under_work_dir(".debug", "inventory_data"),
            "agent_names.json"
        )

        codes: List[str] = []
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    codes = json.load(f)
                log.info(f"从 {path} 加载了 {len(codes)} 个已扫描的代理人")
            except Exception as e:
                log.error(f"加载已扫描代理人列表失败: {e}")

        self._scanned_agent_codes_cache = codes
        self._scanned_agent_codes_timestamp = now
        return codes

    def _create_agent_loader(self) -> 'YamlDataSetLoader[Dict]':
        """创建代理人数据加载器"""
        service = self

        class AgentLoader(YamlDataSetLoader[Dict]):
            def _extract_primary_key(self, data: Dict) -> str:
                return data.get("code", data["agent_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: Dict) -> str:
                return data.get("agent_name", "")

            def _convert_to_object(self, data: Dict) -> Dict:
                return data

            def _validate_data(self, data: Dict) -> bool:
                return isinstance(data, dict) and "agent_name" in data

            def _load_from_memory(self) -> None:
                super()._load_from_memory()

            def _load_from_separated_files(self) -> None:
                super()._load_from_separated_files()

            def _load_from_merged_or_separated(self) -> None:
                super()._load_from_merged_or_separated()

        return AgentLoader("agent")

    def _create_drive_disk_loader(self) -> 'YamlDataSetLoader[Dict]':
        """创建驱动盘数据加载器"""
        service = self

        class DriveDiskLoader(YamlDataSetLoader[Dict]):
            def _extract_primary_key(self, data: Dict) -> str:
                return data.get("code", data["set_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: Dict) -> str:
                return data.get("set_name", "")

            def _convert_to_object(self, data: Dict) -> Dict:
                return data

            def _validate_data(self, data: Dict) -> bool:
                return isinstance(data, dict) and "set_name" in data

            def _load_from_memory(self) -> None:
                super()._load_from_memory()

            def _load_from_separated_files(self) -> None:
                super()._load_from_separated_files()

            def _load_from_merged_or_separated(self) -> None:
                super()._load_from_merged_or_separated()

        return DriveDiskLoader("drive_disk")

    def _create_engine_weapon_loader(self) -> 'YamlDataSetLoader[Dict]':
        """创建音擎数据加载器"""
        service = self

        class EngineWeaponLoader(YamlDataSetLoader[Dict]):
            def _extract_primary_key(self, data: Dict) -> str:
                return data.get("code", data["weapon_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: Dict) -> str:
                return data.get("weapon_name", "")

            def _convert_to_object(self, data: Dict) -> Dict:
                return data

            def _validate_data(self, data: Dict) -> bool:
                return isinstance(data, dict) and "weapon_name" in data

            def _load_from_memory(self) -> None:
                super()._load_from_memory()

            def _load_from_separated_files(self) -> None:
                super()._load_from_separated_files()

            def _load_from_merged_or_separated(self) -> None:
                super()._load_from_merged_or_separated()

        return EngineWeaponLoader("engine_weapon")
