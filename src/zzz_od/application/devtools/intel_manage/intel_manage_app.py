import threading
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.utils import yaml_utils
from one_dragon.utils.log_utils import log
from one_dragon.utils.os_utils import get_resource_path
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.devtools.intel_manage import intel_manage_const
from zzz_od.game_data.agent import AgentTypeEnum, DmgTypeEnum


class AgentData:
    """代理人数据封装类，提供统一的数据访问接口"""
    
    def __init__(self, data: dict):
        self._data = data
    
    @property
    def agent_name(self) -> str:
        return self._data.get('agent_name', '')
    
    @property
    def agent_type(self) -> str:
        return self._data.get('agent_type', '')
    
    @property
    def agent_type_cn(self) -> str:
        return self._data.get('agent_type_cn', '')
    
    @property
    def dmg_type(self) -> str:
        return self._data.get('dmg_type', '')
    
    @property
    def dmg_type_cn(self) -> str:
        return self._data.get('dmg_type_cn', '')
    
    @property
    def rare_type(self) -> str:
        return self._data.get('rare_type', '')
    
    @property
    def code(self) -> str:
        return self._data.get('code', '')
    
    @property
    def weight(self) -> dict:
        return self._data.get('weight', {})
    
    @weight.setter
    def weight(self, value: dict):
        self._data['weight'] = value
    
    def to_dict(self) -> dict:
        """转换为字典形式，用于保存"""
        return dict(self._data)
    
    def update(self, data: dict):
        """更新数据"""
        self._data.update(data)


class DriveDiskData:
    """驱动盘数据封装类，提供统一的数据访问接口"""
    
    def __init__(self, data: dict):
        self._data = data
    
    @property
    def set_name(self) -> str:
        return self._data.get('set_name', '')
    
    @property
    def mission_type_name(self) -> str:
        return self._data.get('mission_type_name', '')
    
    @property
    def code(self) -> str:
        return self._data.get('code', '')
    
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
        return self._data.get('weapon_name', '')
    
    @property
    def rarity(self) -> str:
        return self._data.get('rarity', '')
    
    @property
    def code(self) -> str:
        return self._data.get('code', '')
    
    def to_dict(self) -> dict:
        """转换为字典形式，用于保存"""
        return dict(self._data)
    
    def update(self, data: dict):
        """更新数据"""
        self._data.update(data)


class IntelManageApp(ZApplication):
    """
    信息管理应用（优化版）
    支持多缓存结构和合并文件机制，参考 ScreenLoader 设计模式
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
        
        # ========== Agent 缓存结构（参考 ScreenLoader） ==========
        self.agent_list: List[AgentData] = []              # 列表形式，保持顺序
        self.agent_map: Dict[str, AgentData] = {}          # 名称→对象，快速查找
        self._id_2_agent: Dict[str, AgentData] = {}        # ID/code→对象，内部索引
        
        # ========== Drive Disk 缓存结构 ==========
        self.drive_disk_list: List[DriveDiskData] = []       # 列表形式，保持顺序
        self.drive_disk_map: Dict[str, DriveDiskData] = {}   # 名称→对象，快速查找
        self._id_2_drive_disk: Dict[str, DriveDiskData] = {} # ID/code→对象，内部索引
        
        # ========== Engine Weapon 缓存结构 ==========
        self.engine_weapon_list: List[EngineWeaponData] = []       # 列表形式，保持顺序
        self.engine_weapon_map: Dict[str, EngineWeaponData] = {}   # 名称→对象，快速查找
        self._id_2_engine_weapon: Dict[str, EngineWeaponData] = {} # ID/code→对象，内部索引
        
        # 缓存统计
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        
        # 文件修改时间记录
        self._agent_last_modified_time: float = 0.0
        self._drive_disk_last_modified_time: float = 0.0
        self._engine_weapon_last_modified_time: float = 0.0
        
        # 线程锁：保护并发写入操作
        self._agent_save_lock = threading.Lock()
        self._agent_reload_lock = threading.Lock()
        self._drive_disk_lock = threading.Lock()
        self._engine_weapon_lock = threading.Lock()

    # ========== Agent 路径配置 ==========
    @property
    def agent_yml_dir(self) -> str:
        """获取代理人数据目录路径"""
        return get_resource_path('assets', 'game_data', 'agent')
    
    @property
    def agent_merge_file_path(self) -> str:
        """获取代理人合并文件路径"""
        return str(Path(self.agent_yml_dir) / '_od_merged.yml')
    
    def get_agent_file_path(self, agent_code: str) -> str:
        """获取单个代理人文件路径"""
        return str(Path(self.agent_yml_dir) / f'{agent_code}.yml')
    
    # ========== Drive Disk 路径配置 ==========
    @property
    def drive_disk_yml_dir(self) -> str:
        """获取驱动盘数据目录路径"""
        return get_resource_path('assets', 'game_data', 'drive_disk')
    
    @property
    def drive_disk_merge_file_path(self) -> str:
        """获取驱动盘合并文件路径"""
        return str(Path(self.drive_disk_yml_dir) / '_od_merged.yml')
    
    def get_drive_disk_file_path(self, disk_code: str) -> str:
        """获取单个驱动盘文件路径"""
        return str(Path(self.drive_disk_yml_dir) / f'{disk_code}.yml')
    
    # ========== Engine Weapon 路径配置 ==========
    @property
    def engine_weapon_yml_dir(self) -> str:
        """获取音擎数据目录路径"""
        return get_resource_path('assets', 'game_data', 'engine_weapon')
    
    @property
    def engine_weapon_merge_file_path(self) -> str:
        """获取音擎合并文件路径"""
        return str(Path(self.engine_weapon_yml_dir) / '_od_merged.yml')
    
    def get_engine_weapon_file_path(self, weapon_code: str) -> str:
        """获取单个音擎文件路径"""
        return str(Path(self.engine_weapon_yml_dir) / f'{weapon_code}.yml')

    def _execute(self) -> None:
        log.info('信息管理应用执行')

    # ========== 兼容旧接口 ==========
    def reload(self, from_memory: bool = False, from_separated_files: bool = False) -> None:
        """
        兼容旧接口的重新加载方法（委托给 reload_agent）
        
        Args:
            from_memory: 是否从内存中加载
            from_separated_files: 是否从单独文件加载
        """
        self.reload_agent(from_memory, from_separated_files)
    
    # ========== Agent 数据加载方法 ==========
    def reload_agent(self, from_memory: bool = False, from_separated_files: bool = False) -> None:
        """
        重新加载代理人配置文件（支持多种加载模式）
        
        Args:
            from_memory: 是否从内存中加载（编辑后刷新界面）
            from_separated_files: 是否从单独文件加载（合并配置更新）
        """
        # 使用线程锁保护并发读写（with语句确保锁的正确释放）
        with self._agent_reload_lock:
            try:
                self.agent_list.clear()
                self.agent_map.clear()
                
                if from_memory:
                    # 从内存缓存加载（用于编辑后刷新）
                    log.debug("Reloading agent data from memory")
                    self._cache_hits += 1  # 记录缓存命中
                    for agent in self._id_2_agent.values():
                        self.agent_list.append(agent)
                        self.agent_map[agent.agent_name] = agent
                        
                elif from_separated_files:
                    # 从分离文件加载（用于合并配置更新）
                    log.debug("Reloading agent data from separated files")
                    self._cache_misses += 1  # 记录缓存未命中
                    self._id_2_agent.clear()
                    agent_dir = Path(self.agent_yml_dir)
                    
                    if not agent_dir.exists():
                        log.warning(f"Agent directory not found: {agent_dir}")
                        return
                    
                    agent_type_mapping = self._get_enum_mapping(AgentTypeEnum)
                    dmg_type_mapping = self._get_enum_mapping(DmgTypeEnum)
                    
                    for yml_file in agent_dir.glob('*.yml'):
                        if yml_file.name.startswith('_'):
                            continue
                        
                        if '..' in yml_file.name or '/' in yml_file.name or '\\' in yml_file.name:
                            log.warning(f'Skipping file with illegal characters: {yml_file.name}')
                            continue
                        
                        try:
                            with open(yml_file, 'r', encoding='utf-8') as f:
                                data = yaml.safe_load(f)
                        except (IOError, yaml.YAMLError) as e:
                            log.error(f'Failed to read file {yml_file}: {e}')
                            continue
                        
                        if not isinstance(data, dict) or 'agent_name' not in data:
                            log.warning(f'Invalid agent data format: {yml_file}')
                            continue
                        
                        # 转换类型为中文
                        if 'agent_type' in data and data['agent_type'] in agent_type_mapping:
                            data['agent_type_cn'] = agent_type_mapping[data['agent_type']]
                        else:
                            data['agent_type_cn'] = data.get('agent_type', '')
                        
                        if 'dmg_type' in data and data['dmg_type'] in dmg_type_mapping:
                            data['dmg_type_cn'] = dmg_type_mapping[data['dmg_type']]
                        else:
                            data['dmg_type_cn'] = data.get('dmg_type', '')
                        
                        agent_data = AgentData(data)
                        self.agent_list.append(agent_data)
                        self.agent_map[agent_data.agent_name] = agent_data
                        
                        # 使用 code 作为主键，如果没有 code 则使用 agent_name
                        primary_key = agent_data.code or agent_data.agent_name.lower().replace(' ', '_')
                        self._id_2_agent[primary_key] = agent_data
                        
                    # 更新修改时间
                    self._update_agent_modified_time()
                    
                else:
                    # 默认从合并文件加载（用于应用启动）
                    log.debug("Reloading agent data from merged file")
                    self._cache_misses += 1  # 记录缓存未命中
                    self._id_2_agent.clear()
                    
                    merge_file = Path(self.agent_merge_file_path)
                    if not merge_file.exists():
                        log.warning(f"Merged file not found: {merge_file}")
                        return
                    
                    try:
                        with open(merge_file, 'r', encoding='utf-8') as f:
                            yaml_data = yaml.safe_load(f)
                    except (IOError, yaml.YAMLError) as e:
                        log.error(f'Failed to read merged file: {e}')
                        return
                    
                    if not isinstance(yaml_data, list):
                        log.warning("Merged file format error")
                        return
                    
                    agent_type_mapping = self._get_enum_mapping(AgentTypeEnum)
                    dmg_type_mapping = self._get_enum_mapping(DmgTypeEnum)
                    
                    for data in yaml_data:
                        if not isinstance(data, dict) or 'agent_name' not in data:
                            continue
                        
                        # 转换类型为中文
                        if 'agent_type' in data and data['agent_type'] in agent_type_mapping:
                            data['agent_type_cn'] = agent_type_mapping[data['agent_type']]
                        else:
                            data['agent_type_cn'] = data.get('agent_type', '')
                        
                        if 'dmg_type' in data and data['dmg_type'] in dmg_type_mapping:
                            data['dmg_type_cn'] = dmg_type_mapping[data['dmg_type']]
                        else:
                            data['dmg_type_cn'] = data.get('dmg_type', '')
                        
                        agent_data = AgentData(data)
                        self.agent_list.append(agent_data)
                        self.agent_map[agent_data.agent_name] = agent_data
                        
                        primary_key = agent_data.code or agent_data.agent_name.lower().replace(' ', '_')
                        self._id_2_agent[primary_key] = agent_data
                
                # 更新修改时间
                self._update_agent_modified_time()
                
                # 记录加载日志（包含缓存统计）
                stats = self.get_cache_stats()
                log.info(f"Loaded {len(self.agent_list)} agents | Cache: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate']}% hit rate")
            
            except Exception as e:
                log.error(f'Failed to reload agent data: {e}')
                raise

    # ========== 辅助方法 ==========
    def _get_latest_mtime(self, directory: Path) -> float:
        """获取目录下所有yml文件的最新修改时间"""
        latest_mtime = 0.0
        try:
            for yml_file in directory.glob('*.yml'):
                if not yml_file.name.startswith('_'):
                    mtime = yml_file.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime = mtime
        except OSError as e:
            log.error(f'Failed to get file modification time: {e}')
        return latest_mtime
    
    # ========== Agent 修改时间方法 ==========
    def _update_agent_modified_time(self) -> None:
        """更新代理人文件修改时间记录"""
        agent_dir = Path(self.agent_yml_dir)
        if agent_dir.exists():
            self._agent_last_modified_time = self._get_latest_mtime(agent_dir)
        else:
            self._agent_last_modified_time = 0.0
    
    # ========== Drive Disk 数据加载方法 ==========
    def reload_drive_disk(self, from_memory: bool = False, from_separated_files: bool = False) -> None:
        """
        重新加载驱动盘配置文件（支持多种加载模式）
        
        Args:
            from_memory: 是否从内存中加载（编辑后刷新界面）
            from_separated_files: 是否从单独文件加载（合并配置更新）
        """
        with self._drive_disk_lock:
            self.drive_disk_list.clear()
            self.drive_disk_map.clear()
            
            if from_memory:
                log.debug("Reloading drive disk data from memory")
                self._cache_hits += 1
                for disk in self._id_2_drive_disk.values():
                    self.drive_disk_list.append(disk)
                    self.drive_disk_map[disk.set_name] = disk
                    
            elif from_separated_files:
                log.debug("Reloading drive disk data from separated files")
                self._cache_misses += 1
                self._id_2_drive_disk.clear()
                disk_dir = Path(self.drive_disk_yml_dir)
                
                if not disk_dir.exists():
                    log.warning(f"Drive disk directory not found: {disk_dir}")
                    return
                
                for yml_file in disk_dir.glob('*.yml'):
                    if yml_file.name.startswith('_'):
                        continue
                    
                    if '..' in yml_file.name or '/' in yml_file.name or '\\' in yml_file.name:
                        log.warning(f'Skipping file with illegal characters: {yml_file.name}')
                        continue
                    
                    try:
                        with open(yml_file, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f)
                    except (IOError, yaml.YAMLError) as e:
                        log.error(f'Failed to read file {yml_file}: {e}')
                        continue
                    
                    if not isinstance(data, dict) or 'set_name' not in data:
                        log.warning(f'Invalid drive disk data format: {yml_file}')
                        continue
                    
                    disk_data = DriveDiskData(data)
                    self.drive_disk_list.append(disk_data)
                    self.drive_disk_map[disk_data.set_name] = disk_data
                    
                    primary_key = disk_data.code or disk_data.set_name.lower().replace(' ', '_')
                    self._id_2_drive_disk[primary_key] = disk_data
                
                self._update_drive_disk_modified_time()
                
            else:
                log.debug("Reloading drive disk data from merged file")
                self._cache_misses += 1
                self._id_2_drive_disk.clear()
                
                merge_file = Path(self.drive_disk_merge_file_path)
                if not merge_file.exists():
                    # 如果合并文件不存在，从分离文件加载
                    self.reload_drive_disk(from_separated_files=True)
                    return
                
                try:
                    with open(merge_file, 'r', encoding='utf-8') as f:
                        yaml_data = yaml.safe_load(f)
                except (IOError, yaml.YAMLError) as e:
                    log.error(f'Failed to read merged file: {e}')
                    return
                
                if not isinstance(yaml_data, list):
                    log.warning("Drive disk merged file format error")
                    return
                
                for data in yaml_data:
                    if not isinstance(data, dict) or 'set_name' not in data:
                        continue
                    
                    disk_data = DriveDiskData(data)
                    self.drive_disk_list.append(disk_data)
                    self.drive_disk_map[disk_data.set_name] = disk_data
                    
                    primary_key = disk_data.code or disk_data.set_name.lower().replace(' ', '_')
                    self._id_2_drive_disk[primary_key] = disk_data
            
            self._update_drive_disk_modified_time()
            stats = self.get_cache_stats()
            log.info(f"Loaded {len(self.drive_disk_list)} drive disks | Cache: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate']}% hit rate")
    
    def _update_drive_disk_modified_time(self) -> None:
        """更新驱动盘文件修改时间记录"""
        disk_dir = Path(self.drive_disk_yml_dir)
        if disk_dir.exists():
            self._drive_disk_last_modified_time = self._get_latest_mtime(disk_dir)
        else:
            self._drive_disk_last_modified_time = 0.0
    
    # ========== Engine Weapon 数据加载方法 ==========
    def reload_engine_weapon(self, from_memory: bool = False, from_separated_files: bool = False) -> None:
        """
        重新加载音擎配置文件（支持多种加载模式）
        
        Args:
            from_memory: 是否从内存中加载（编辑后刷新界面）
            from_separated_files: 是否从单独文件加载（合并配置更新）
        """
        with self._engine_weapon_lock:
            self.engine_weapon_list.clear()
            self.engine_weapon_map.clear()
            
            if from_memory:
                log.debug("Reloading engine weapon data from memory")
                self._cache_hits += 1
                for weapon in self._id_2_engine_weapon.values():
                    self.engine_weapon_list.append(weapon)
                    self.engine_weapon_map[weapon.weapon_name] = weapon
                    
            elif from_separated_files:
                log.debug("Reloading engine weapon data from separated files")
                self._cache_misses += 1
                self._id_2_engine_weapon.clear()
                weapon_dir = Path(self.engine_weapon_yml_dir)
                
                if not weapon_dir.exists():
                    log.warning(f"Engine weapon directory not found: {weapon_dir}")
                    return
                
                for yml_file in weapon_dir.glob('*.yml'):
                    if yml_file.name.startswith('_'):
                        continue
                    
                    if '..' in yml_file.name or '/' in yml_file.name or '\\' in yml_file.name:
                        log.warning(f'Skipping file with illegal characters: {yml_file.name}')
                        continue
                    
                    try:
                        with open(yml_file, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f)
                    except (IOError, yaml.YAMLError) as e:
                        log.error(f'Failed to read file {yml_file}: {e}')
                        continue
                    
                    if not isinstance(data, dict) or 'weapon_name' not in data:
                        log.warning(f'Invalid engine weapon data format: {yml_file}')
                        continue
                    
                    weapon_data = EngineWeaponData(data)
                    self.engine_weapon_list.append(weapon_data)
                    self.engine_weapon_map[weapon_data.weapon_name] = weapon_data
                    
                    primary_key = weapon_data.code or weapon_data.weapon_name.lower().replace(' ', '_')
                    self._id_2_engine_weapon[primary_key] = weapon_data
                
                self._update_engine_weapon_modified_time()
                
            else:
                log.debug("Reloading engine weapon data from merged file")
                self._cache_misses += 1
                self._id_2_engine_weapon.clear()
                
                merge_file = Path(self.engine_weapon_merge_file_path)
                if not merge_file.exists():
                    # 如果合并文件不存在，从分离文件加载
                    self.reload_engine_weapon(from_separated_files=True)
                    return
                
                try:
                    with open(merge_file, 'r', encoding='utf-8') as f:
                        yaml_data = yaml.safe_load(f)
                except (IOError, yaml.YAMLError) as e:
                    log.error(f'Failed to read merged file: {e}')
                    return
                
                if not isinstance(yaml_data, list):
                    log.warning("Engine weapon merged file format error")
                    return
                
                for data in yaml_data:
                    if not isinstance(data, dict) or 'weapon_name' not in data:
                        continue
                    
                    weapon_data = EngineWeaponData(data)
                    self.engine_weapon_list.append(weapon_data)
                    self.engine_weapon_map[weapon_data.weapon_name] = weapon_data
                    
                    primary_key = weapon_data.code or weapon_data.weapon_name.lower().replace(' ', '_')
                    self._id_2_engine_weapon[primary_key] = weapon_data
            
            self._update_engine_weapon_modified_time()
            stats = self.get_cache_stats()
            log.info(f"Loaded {len(self.engine_weapon_list)} engine weapons | Cache: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate']}% hit rate")
    
    def _update_engine_weapon_modified_time(self) -> None:
        """更新音擎文件修改时间记录"""
        weapon_dir = Path(self.engine_weapon_yml_dir)
        if weapon_dir.exists():
            self._engine_weapon_last_modified_time = self._get_latest_mtime(weapon_dir)
        else:
            self._engine_weapon_last_modified_time = 0.0

    def get_agent(self, agent_name: str, copy: bool = False) -> Optional[AgentData]:
        """
        获取代理人数据
        
        Args:
            agent_name: 代理人名称
            copy: 是否复制（用于管理界面临时修改）
        
        Returns:
            AgentData 实例或 None
        """
        agent = self.agent_map.get(agent_name)
        if agent is None:
            return None
        
        if copy:
            return AgentData(agent.to_dict())
        return agent

    def save_agent(self, agent_data: AgentData, reload_after_save: bool = True) -> bool:
        """
        保存单个代理人数据（同时保存到分离文件和合并文件）
        
        Args:
            agent_data: 代理人数据
            reload_after_save: 是否在保存后重新加载
        
        Returns:
            是否保存成功
        """
        # 使用线程锁保护并发写入
        with self._agent_save_lock:
            try:
                agent_dir = Path(self.agent_yml_dir)
                agent_dir.mkdir(parents=True, exist_ok=True)
                
                # 使用 code 作为文件名，如果没有 code 则使用 agent_name
                primary_key = agent_data.code or agent_data.agent_name.lower().replace(' ', '_')
                file_path = agent_dir / f'{primary_key}.yml'
                
                # 保存到分离文件
                yaml_op = YamlOperator(str(file_path))
                yaml_op.data = agent_data.to_dict()
                yaml_op.save()
                
                # 更新内存缓存
                self._id_2_agent[primary_key] = agent_data
                self.agent_map[agent_data.agent_name] = agent_data
                
                # 更新列表中的数据
                for i, agent in enumerate(self.agent_list):
                    if agent.agent_name == agent_data.agent_name:
                        self.agent_list[i] = agent_data
                        break
                
                # 保存到合并文件
                self._save_to_merge_file()
                
                log.info(f"Saved agent data to: {file_path}")
                
                if reload_after_save:
                    self.reload(from_memory=True)
                
                return True
            except (IOError, OSError, yaml.YAMLError) as e:
                log.error(f'Failed to save agent data: {e}')
                return False

    def _save_to_merge_file(self) -> None:
        """保存所有代理人数据到合并文件（带错误恢复机制）"""
        merge_file = Path(self.agent_merge_file_path)
        temp_file = merge_file.with_suffix('.tmp')
        
        try:
            # 确保父目录存在
            merge_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 生成数据
            all_data = [agent.to_dict() for agent in self.agent_list]
            
            # 原子写入：先写临时文件，再替换
            with open(temp_file, 'w', encoding='utf-8') as f:
                yaml.dump(all_data, f, allow_unicode=True, indent=2)
            
            # 替换目标文件（原子操作）
            temp_file.replace(merge_file)
            
            log.debug(f"Saved merged data to: {merge_file}")
            
        except (IOError, OSError, yaml.YAMLError) as e:
            log.error(f'Failed to save merged file: {e}')
            
            # 清理残留的临时文件
            self._cleanup_temp_file(temp_file)
            
        finally:
            # 确保临时文件被清理（即使发生未预期的异常）
            self._cleanup_temp_file(temp_file)
    
    def _cleanup_temp_file(self, temp_file: Path) -> None:
        """清理临时文件（错误恢复辅助方法）"""
        try:
            if temp_file.exists():
                temp_file.unlink()
                log.debug(f"Cleaned up temporary file: {temp_file}")
        except (IOError, OSError) as e:
            log.warning(f"Failed to cleanup temporary file {temp_file}: {e}")

    def delete_agent(self, agent_name: str) -> bool:
        """
        删除代理人数据
        
        Args:
            agent_name: 代理人名称
        
        Returns:
            是否删除成功
        """
        agent = self.agent_map.get(agent_name)
        if agent is None:
            log.warning(f"Agent not found: {agent_name}")
            return False
        
        try:
            # 从内存移除
            primary_key = agent.code or agent_name.lower().replace(' ', '_')
            del self._id_2_agent[primary_key]
            del self.agent_map[agent_name]
            
            # 从列表移除
            self.agent_list = [a for a in self.agent_list if a.agent_name != agent_name]
            
            # 删除文件
            file_path = Path(self.get_agent_file_path(primary_key))
            if file_path.exists():
                file_path.unlink()
            
            # 更新合并文件
            self._save_to_merge_file()
            
            log.info(f"Deleted agent: {agent_name}")
            return True
        except (IOError, OSError, KeyError) as e:
            log.error(f'Failed to delete agent: {e}')
            return False

    def update_from_separated_files(self) -> None:
        """从分离文件更新并保存到合并文件（类似屏幕管理的合并功能）"""
        self.reload(from_separated_files=True)
        self._save_to_merge_file()

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息（暴露给监控系统）"""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total) * 100 if total > 0 else 0
        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'hit_rate': round(hit_rate, 2),
            'total': total
        }
    
    def reset_cache_stats(self) -> None:
        """重置缓存统计信息（用于监控系统定期清理）"""
        self._cache_hits = 0
        self._cache_misses = 0
    
    def log_cache_stats(self) -> None:
        """记录缓存统计日志（用于监控和调试）"""
        stats = self.get_cache_stats()
        log.info(f"Cache Statistics - Hits: {stats['hits']}, Misses: {stats['misses']}, "
                f"Hit Rate: {stats['hit_rate']}%, Total: {stats['total']}")

    def _get_enum_mapping(self, enum_class) -> Dict[str, str]:
        """获取枚举类型映射（英文名称到中文值），排除UNKNOWN"""
        return {e.name: e.value for e in enum_class if e.name != 'UNKNOWN'}

    def get_agent_type_mapping(self) -> Dict[str, str]:
        """获取角色类型映射（英文到中文）"""
        return self._get_enum_mapping(AgentTypeEnum)

    def get_dmg_type_mapping(self) -> Dict[str, str]:
        """获取属性类型映射（英文到中文）"""
        return self._get_enum_mapping(DmgTypeEnum)
