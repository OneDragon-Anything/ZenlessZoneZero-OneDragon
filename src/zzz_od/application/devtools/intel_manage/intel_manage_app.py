import threading
from pathlib import Path
from typing import Optional

import yaml

from one_dragon.base.config.yaml_data_set_loader import YamlDataSetLoader
from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.utils.log_utils import log
from one_dragon.utils.os_utils import get_resource_path
from zzz_od.application.devtools.intel_manage import intel_manage_const
from zzz_od.application.devtools.intel_manage.intel_manage_config import (
    IntelManageConfig as Config,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentTypeEnum, DmgTypeEnum


class AgentData:
    """代理人数据封装类，提供统一的数据访问接口"""

    def __init__(self, data: dict):
        self._data = data

    @property
    def agent_name(self) -> str:
        return self._data.get("agent_name", "")

    @property
    def agent_type(self) -> str:
        return self._data.get("agent_type", "")

    @property
    def agent_type_cn(self) -> str:
        return self._data.get("agent_type_cn", "")

    @property
    def dmg_type(self) -> str:
        return self._data.get("dmg_type", "")

    @property
    def dmg_type_cn(self) -> str:
        return self._data.get("dmg_type_cn", "")

    @property
    def rare_type(self) -> str:
        return self._data.get("rare_type", "")

    @property
    def code(self) -> str:
        return self._data.get("code", "")

    @property
    def weight(self) -> dict:
        return self._data.get("weight", {})

    @weight.setter
    def weight(self, value: dict):
        self._data["weight"] = value

    @property
    def recommend_engine_weapon(self) -> list:
        return self._data.get("recommend_engine_weapon", [])

    @recommend_engine_weapon.setter
    def recommend_engine_weapon(self, value: list):
        self._data["recommend_engine_weapon"] = value

    def to_dict(self) -> dict:
        """转换为字典形式，用于保存（排除派生字段）"""
        data = dict(self._data)
        data.pop("agent_type_cn", None)
        data.pop("dmg_type_cn", None)
        return data

    def update(self, data: dict):
        """更新数据"""
        self._data.update(data)


class DriveDiskData:
    """驱动盘数据封装类，提供统一的数据访问接口"""

    def __init__(self, data: dict):
        self._data = data

    @property
    def set_name(self) -> str:
        return self._data.get("set_name", "")

    @property
    def mission_type_name(self) -> str:
        return self._data.get("mission_type_name", "")

    @property
    def code(self) -> str:
        return self._data.get("code", "")

    def to_dict(self) -> dict:
        """转换为字典形式，用于保存"""
        return dict(self._data)

    def update(self, data: dict):
        """更新数据"""
        self._data.update(data)


class EngineWeaponData:
    """音擎数据封装类，提供统一的数据访问接口"""

    def __init__(self, data: dict):
        self._data = data

    @property
    def weapon_name(self) -> str:
        return self._data.get("weapon_name", "")

    @property
    def rarity(self) -> str:
        return self._data.get("rarity", "")

    @property
    def code(self) -> str:
        return self._data.get("code", "")

    def to_dict(self) -> dict:
        """转换为字典形式，用于保存"""
        return dict(self._data)

    def update(self, data: dict):
        """更新数据"""
        self._data.update(data)


class IntelManageApp(ZApplication):
    """
    信息管理应用（优化版）
    支持多缓存结构和合并文件机制，使用 YamlDataSetLoader 基类
    """

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=intel_manage_const.APP_ID,
            op_name=intel_manage_const.APP_NAME,
            node_max_retry_times=1,
            timeout_seconds=-1,
            op_callback=None,
            need_check_game_win=False,
        )

        self._cache_hits: int = 0
        self._cache_misses: int = 0

        self._agent_last_modified_time: float = 0.0
        self._drive_disk_last_modified_time: float = 0.0
        self._engine_weapon_last_modified_time: float = 0.0

        self._agent_save_lock = threading.Lock()
        self._agent_reload_lock = threading.RLock()
        self._drive_disk_lock = threading.Lock()
        self._engine_weapon_lock = threading.Lock()

        # 创建数据集加载器
        self.agent_loader = self._create_agent_loader()
        self.drive_disk_loader = self._create_drive_disk_loader()
        self.engine_weapon_loader = self._create_engine_weapon_loader()

    def _create_agent_loader(self) -> YamlDataSetLoader:
        """创建角色数据加载器"""
        app = self

        class AgentLoader(YamlDataSetLoader):
            def _extract_primary_key(self, data: dict) -> str:
                return data.get("code", data["agent_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: dict) -> str:
                return data.get("agent_name", "")

            def _convert_to_object(self, data: dict) -> AgentData:
                # 处理枚举映射
                agent_type_mapping = app._get_enum_mapping(AgentTypeEnum)
                dmg_type_mapping = app._get_enum_mapping(DmgTypeEnum)

                if "agent_type" in data and data["agent_type"] in agent_type_mapping:
                    data["agent_type_cn"] = agent_type_mapping[data["agent_type"]]
                else:
                    data["agent_type_cn"] = data.get("agent_type", "")

                if "dmg_type" in data and data["dmg_type"] in dmg_type_mapping:
                    data["dmg_type_cn"] = dmg_type_mapping[data["dmg_type"]]
                else:
                    data["dmg_type_cn"] = data.get("dmg_type", "")

                return AgentData(data)

            def _validate_data(self, data: dict) -> bool:
                return isinstance(data, dict) and "agent_name" in data

            def load(
                self, from_memory: bool = False, from_separated_files: bool = False
            ) -> None:
                with app._agent_reload_lock:
                    app._cache_misses += 1
                    super().load(from_memory, from_separated_files)
                    app._update_agent_modified_time()
                    stats = app.get_cache_stats()
                    log.info(
                        f"Loaded {len(self.data_list)} agents | Cache: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate']}% hit rate"
                    )

        return AgentLoader(Config.AGENT_DIR_NAME)

    def _create_drive_disk_loader(self) -> YamlDataSetLoader:
        """创建驱动盘数据加载器"""
        app = self

        class DriveDiskLoader(YamlDataSetLoader):
            def _extract_primary_key(self, data: dict) -> str:
                return data.get("code", data["set_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: dict) -> str:
                return data.get("set_name", "")

            def _convert_to_object(self, data: dict) -> DriveDiskData:
                return DriveDiskData(data)

            def _validate_data(self, data: dict) -> bool:
                return isinstance(data, dict) and "set_name" in data

            def load(
                self, from_memory: bool = False, from_separated_files: bool = False
            ) -> None:
                with app._drive_disk_lock:
                    app._cache_misses += 1
                    super().load(from_memory, from_separated_files)
                    app._update_drive_disk_modified_time()
                    stats = app.get_cache_stats()
                    log.info(
                        f"Loaded {len(self.data_list)} drive disks | Cache: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate']}% hit rate"
                    )

        return DriveDiskLoader(Config.DRIVE_DISK_DIR_NAME)

    def _create_engine_weapon_loader(self) -> YamlDataSetLoader:
        """创建音擎数据加载器"""
        app = self

        class EngineWeaponLoader(YamlDataSetLoader):
            def _extract_primary_key(self, data: dict) -> str:
                return data.get("code", data["weapon_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: dict) -> str:
                return data.get("weapon_name", "")

            def _convert_to_object(self, data: dict) -> EngineWeaponData:
                return EngineWeaponData(data)

            def _validate_data(self, data: dict) -> bool:
                return isinstance(data, dict) and "weapon_name" in data

            def load(
                self, from_memory: bool = False, from_separated_files: bool = False
            ) -> None:
                with app._engine_weapon_lock:
                    app._cache_misses += 1
                    super().load(from_memory, from_separated_files)
                    app._update_engine_weapon_modified_time()
                    stats = app.get_cache_stats()
                    log.info(
                        f"Loaded {len(self.data_list)} engine weapons | Cache: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate']}% hit rate"
                    )

        return EngineWeaponLoader(Config.ENGINE_WEAPON_DIR_NAME)

    # 兼容旧代码的属性代理
    @property
    def agent_list(self) -> list[AgentData]:
        return self.agent_loader.data_list

    @property
    def agent_map(self) -> dict[str, AgentData]:
        return self.agent_loader.data_map

    @property
    def _id_2_agent(self) -> dict[str, AgentData]:
        return self.agent_loader._id_2_data

    @property
    def drive_disk_list(self) -> list[DriveDiskData]:
        return self.drive_disk_loader.data_list

    @property
    def drive_disk_map(self) -> dict[str, DriveDiskData]:
        return self.drive_disk_loader.data_map

    @property
    def _id_2_drive_disk(self) -> dict[str, DriveDiskData]:
        return self.drive_disk_loader._id_2_data

    @property
    def engine_weapon_list(self) -> list[EngineWeaponData]:
        return self.engine_weapon_loader.data_list

    @property
    def engine_weapon_map(self) -> dict[str, EngineWeaponData]:
        return self.engine_weapon_loader.data_map

    @property
    def _id_2_engine_weapon(self) -> dict[str, EngineWeaponData]:
        return self.engine_weapon_loader._id_2_data

    @property
    def agent_yml_dir(self) -> str:
        return get_resource_path("assets", "game_data", Config.AGENT_DIR_NAME)

    @property
    def agent_merge_file_path(self) -> str:
        return str(Path(self.agent_yml_dir) / Config.MERGED_FILE_NAME)

    def get_agent_file_path(self, agent_code: str) -> str:
        return str(Path(self.agent_yml_dir) / f"{agent_code}.yml")

    @property
    def drive_disk_yml_dir(self) -> str:
        return get_resource_path("assets", "game_data", Config.DRIVE_DISK_DIR_NAME)

    @property
    def drive_disk_merge_file_path(self) -> str:
        return str(Path(self.drive_disk_yml_dir) / Config.MERGED_FILE_NAME)

    def get_drive_disk_file_path(self, disk_code: str) -> str:
        return str(Path(self.drive_disk_yml_dir) / f"{disk_code}.yml")

    @property
    def engine_weapon_yml_dir(self) -> str:
        return get_resource_path("assets", "game_data", Config.ENGINE_WEAPON_DIR_NAME)

    @property
    def engine_weapon_merge_file_path(self) -> str:
        return str(Path(self.engine_weapon_yml_dir) / Config.MERGED_FILE_NAME)

    def get_engine_weapon_file_path(self, weapon_code: str) -> str:
        return str(Path(self.engine_weapon_yml_dir) / f"{weapon_code}.yml")

    def _execute(self) -> None:
        log.info("信息管理应用执行")

    def reload(
        self, from_memory: bool = False, from_separated_files: bool = False
    ) -> None:
        self.agent_loader.load(from_memory, from_separated_files)

    def reload_agent(
        self, from_memory: bool = False, from_separated_files: bool = False
    ) -> None:
        self.agent_loader.load(from_memory, from_separated_files)

    def _get_latest_mtime(self, directory: Path) -> float:
        latest_mtime = 0.0
        try:
            for yml_file in directory.glob("*.yml"):
                if not yml_file.name.startswith("_"):
                    mtime = yml_file.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime = mtime
        except OSError as e:
            log.error(f"Failed to get file modification time: {e}")
        return latest_mtime

    def _update_agent_modified_time(self) -> None:
        agent_dir = Path(self.agent_yml_dir)
        if agent_dir.exists():
            self._agent_last_modified_time = self._get_latest_mtime(agent_dir)
        else:
            self._agent_last_modified_time = 0.0

    def reload_drive_disk(
        self, from_memory: bool = False, from_separated_files: bool = False
    ) -> None:
        self.drive_disk_loader.load(from_memory, from_separated_files)

    def reload_engine_weapon(
        self, from_memory: bool = False, from_separated_files: bool = False
    ) -> None:
        self.engine_weapon_loader.load(from_memory, from_separated_files)

    def get_agent(self, agent_name: str, copy: bool = False) -> AgentData | None:
        agent = self.agent_map.get(agent_name)
        if agent is None:
            return None

        if copy:
            return AgentData(agent.to_dict())
        return agent

    def save_agent(self, agent_data: AgentData, reload_after_save: bool = True) -> bool:
        with self._agent_save_lock:
            try:
                agent_dir = Path(self.agent_yml_dir)
                agent_dir.mkdir(parents=True, exist_ok=True)

                primary_key = agent_data.code or agent_data.agent_name.lower().replace(
                    " ", "_"
                )
                file_path = agent_dir / f"{primary_key}.yml"

                yaml_op = YamlOperator(str(file_path))
                yaml_op.data = agent_data.to_dict()
                yaml_op.save()

                self.agent_loader.update_data(agent_data, agent_data.to_dict())
                self.agent_loader.save_to_merge_file()

                log.info(f"Saved agent data to: {file_path}")

                if reload_after_save:
                    self.reload(from_memory=True)

                return True
            except (OSError, yaml.YAMLError) as e:
                log.error(f"Failed to save agent data: {e}")
                return False

    def delete_agent(self, agent_name: str) -> bool:
        agent = self.agent_map.get(agent_name)
        if agent is None:
            log.warning(f"Agent not found: {agent_name}")
            return False

        try:
            primary_key = agent.code or agent_name.lower().replace(" ", "_")

            file_path = Path(self.get_agent_file_path(primary_key))
            if file_path.exists():
                file_path.unlink()

            # 重新加载数据
            self.agent_loader.load(from_separated_files=True)
            self.agent_loader.save_to_merge_file()

            log.info(f"Deleted agent: {agent_name}")
            return True
        except (OSError, KeyError) as e:
            log.error(f"Failed to delete agent: {e}")
            return False

    def update_from_separated_files(self) -> None:
        self.reload(from_separated_files=True)
        self.agent_loader.save_to_merge_file()

    def get_cache_stats(self) -> dict:
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total) * 100 if total > 0 else 0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": round(hit_rate, 2),
            "total": total,
        }

    def reset_cache_stats(self) -> None:
        self._cache_hits = 0
        self._cache_misses = 0

    def log_cache_stats(self) -> None:
        stats = self.get_cache_stats()
        log.info(
            f"Cache Statistics - Hits: {stats['hits']}, Misses: {stats['misses']}, "
            f"Hit Rate: {stats['hit_rate']}%, Total: {stats['total']}"
        )

    def _get_enum_mapping(self, enum_class) -> dict[str, str]:
        return {e.name: e.value for e in enum_class if e.name != "UNKNOWN"}

    def get_agent_type_mapping(self) -> dict[str, str]:
        return self._get_enum_mapping(AgentTypeEnum)

    def get_dmg_type_mapping(self) -> dict[str, str]:
        return self._get_enum_mapping(DmgTypeEnum)
