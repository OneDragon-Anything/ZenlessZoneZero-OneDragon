import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

import yaml

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log

T = TypeVar('T')  # 数据项类型


class YamlDataSetLoader(ABC, Generic[T]):
    """
    YAML数据集加载器基类（模板方法模式）
    
    核心特性：
    - 三模式加载：from_memory -> from_separated_files -> merged_file
    - 内存映射缓存：_id_2_data 字典存储原始数据
    - 线程安全：使用 RLock 保证并发安全
    - 优先读取合并文件以减少 IO 操作
    """

    MERGED_FILE_NAME: str = "_od_merged.yml"

    def __init__(self, data_dir_name: str):
        """
        初始化数据集加载器

        Args:
            data_dir_name: 数据目录名称（相对于 assets/game_data/）
        """
        self.data_dir = os_utils.get_path_under_work_dir("assets", "game_data", data_dir_name)
        self.merge_file_path = str(Path(self.data_dir) / self.MERGED_FILE_NAME)

        # 内存映射
        self._id_2_data: dict[str, T] = {}
        self._data_list: list[T] = []
        self._data_map: dict[str, T] = {}

        # 线程锁
        self._load_lock = threading.RLock()

    @property
    def data_list(self) -> list[T]:
        return self._data_list

    @property
    def data_map(self) -> dict[str, T]:
        return self._data_map

    def clear(self) -> None:
        """清空所有数据"""
        with self._load_lock:
            self._id_2_data.clear()
            self._data_list.clear()
            self._data_map.clear()

    @abstractmethod
    def _extract_primary_key(self, data: dict) -> str:
        """
        提取数据的主键（子类必须实现）

        Args:
            data: 原始数据字典

        Returns:
            str: 主键值
        """
        pass

    @abstractmethod
    def _extract_name_key(self, data: dict) -> str:
        """
        提取数据的名称键（子类必须实现）

        Args:
            data: 原始数据字典

        Returns:
            str: 名称键值
        """
        pass

    @abstractmethod
    def _convert_to_object(self, data: dict) -> T:
        """
        将原始字典数据转换为目标对象（子类必须实现）

        Args:
            data: 原始数据字典

        Returns:
            T: 转换后的对象
        """
        pass

    def _preprocess_data(self, data: dict) -> dict:
        """
        预处理数据（子类可选实现）

        Args:
            data: 原始数据字典

        Returns:
            dict: 处理后的数据字典
        """
        return data

    def get_data_file_path(self, primary_key: str) -> str:
        """
        获取单个数据文件的路径

        Args:
            primary_key: 主键

        Returns:
            str: 文件路径
        """
        return str(Path(self.data_dir) / f"{primary_key}.yml")

    def load(
        self,
        from_memory: bool = False,
        from_separated_files: bool = False
    ) -> None:
        """
        加载数据（模板方法）

        Args:
            from_memory: 是否从内存缓存加载
            from_separated_files: 是否从单独文件加载
        """
        with self._load_lock:
            self.data_list.clear()
            self.data_map.clear()

            if from_memory:
                log.debug(f"Loading data from memory: {self.data_dir}")
                self._load_from_memory()
            elif from_separated_files:
                log.debug(f"Loading data from separated files: {self.data_dir}")
                self._load_from_separated_files()
            else:
                log.debug(f"Loading data from merged file: {self.data_dir}")
                self._load_from_merged_or_separated()

    def _load_from_memory(self) -> None:
        """从内存缓存加载数据"""
        for data_item in self._id_2_data.values():
            self.data_list.append(data_item)
            name_key = self._extract_name_key_from_object(data_item)
            if name_key:
                self.data_map[name_key] = data_item

    def _load_from_separated_files(self) -> None:
        """从单独文件加载数据"""
        self._id_2_data.clear()
        data_dir = Path(self.data_dir)

        if not data_dir.exists():
            log.warning(f"Data directory not found: {data_dir}")
            return

        for yml_file in data_dir.glob("*.yml"):
            if yml_file.name.startswith("_"):
                continue

            if ".." in yml_file.name or "/" in yml_file.name or "\\" in yml_file.name:
                log.warning(f"Skipping file with illegal characters: {yml_file.name}")
                continue

            try:
                with open(yml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except Exception as e:
                log.error(f"Failed to read file {yml_file}: {e}")
                continue

            if not self._validate_data(data):
                log.warning(f"Invalid data format: {yml_file}")
                continue

            processed_data = self._preprocess_data(data)
            data_item = self._convert_to_object(processed_data)
            self._add_data_item(data_item, processed_data)

    def _load_from_merged_or_separated(self) -> None:
        """从合并文件加载，如果失败则回退到单独文件"""
        self._id_2_data.clear()
        merge_file = Path(self.merge_file_path)

        if not merge_file.exists():
            self.load(from_separated_files=True)
            return

        try:
            with open(merge_file, encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
        except Exception as e:
            log.error(f"Failed to read merged file: {e}")
            self.load(from_separated_files=True)
            return

        if not isinstance(yaml_data, list):
            log.warning("Merged file format error, expected list")
            self.load(from_separated_files=True)
            return

        if len(yaml_data) == 0:
            self.load(from_separated_files=True)
            return

        for data in yaml_data:
            if not self._validate_data(data):
                continue

            processed_data = self._preprocess_data(data)
            data_item = self._convert_to_object(processed_data)
            self._add_data_item(data_item, processed_data)

    def _validate_data(self, data: dict) -> bool:
        """
        验证数据是否有效（子类可选重写）

        Args:
            data: 数据字典

        Returns:
            bool: 是否有效
        """
        return isinstance(data, dict)

    def _add_data_item(self, data_item: T, original_data: dict) -> None:
        """
        添加数据项到内存中

        Args:
            data_item: 数据项对象
            original_data: 原始数据字典
        """
        self.data_list.append(data_item)

        name_key = self._extract_name_key_from_object(data_item)
        if name_key:
            self.data_map[name_key] = data_item

        primary_key = self._extract_primary_key(original_data)
        self._id_2_data[primary_key] = data_item

    def _extract_name_key_from_object(self, data_item: T) -> str | None:
        """
        从对象中提取名称键（子类可选重写）
        默认从原始数据字典中提取

        Args:
            data_item: 数据项对象

        Returns:
            Optional[str]: 名称键，可能为None
        """
        # 默认尝试将对象转回字典后提取
        try:
            if hasattr(data_item, 'to_dict'):
                data_dict = data_item.to_dict()
            elif hasattr(data_item, '_data'):
                data_dict = data_item._data
            else:
                data_dict = dict(data_item) if isinstance(data_item, dict) else {}

            return self._extract_name_key(data_dict)
        except Exception:
            return None

    def get_by_name(self, name: str) -> T | None:
        """
        根据名称获取数据

        Args:
            name: 名称

        Returns:
            Optional[T]: 数据项，未找到返回None
        """
        return self.data_map.get(name)

    def get_by_code(self, code: str) -> T | None:
        """
        根据主键获取数据

        Args:
            code: 主键

        Returns:
            Optional[T]: 数据项，未找到返回None
        """
        return self._id_2_data.get(code)

    def get_all(self) -> list[T]:
        """
        获取所有数据

        Returns:
            List[T]: 所有数据项
        """
        return list(self.data_list)

    def update_data(self, data_item: T, original_data: dict) -> None:
        """
        更新数据项

        Args:
            data_item: 更新后的数据项对象
            original_data: 原始数据字典
        """
        with self._load_lock:
            name_key = self._extract_name_key_from_object(data_item)
            primary_key = self._extract_primary_key(original_data)

            # 更新内存映射
            self._id_2_data[primary_key] = data_item
            if name_key:
                self.data_map[name_key] = data_item

            # 更新列表
            found = False
            for i, item in enumerate(self._data_list):
                item_name_key = self._extract_name_key_from_object(item)
                if item_name_key == name_key:
                    self._data_list[i] = data_item
                    found = True
                    break
            
            # 如果没有找到，则添加到列表
            if not found:
                self._data_list.append(data_item)

    def save_to_merge_file(self) -> None:
        """
        将所有数据保存到合并文件（优化：使用原子操作和文件锁）
        """
        merge_file = Path(self.merge_file_path)
        temp_file = merge_file.with_suffix(".tmp")
        
        # 使用 RLock 确保线程安全
        with self._load_lock:
            try:
                merge_file.parent.mkdir(parents=True, exist_ok=True)

                all_data = []
                # 从 _id_2_data 获取所有数据，确保保存完整的数据集
                for key, data_item in self._id_2_data.items():
                    try:
                        if hasattr(data_item, 'to_dict'):
                            all_data.append(data_item.to_dict())
                        elif hasattr(data_item, '_data'):
                            all_data.append(data_item._data)
                        elif isinstance(data_item, dict):
                            all_data.append(data_item)
                    except Exception as e:
                        log.warning(f"Failed to convert data item {key}: {e}")
                        continue

                # 如果没有任何数据，先尝试从分离文件加载
                if not all_data:
                    log.warning(f"No data in memory cache, trying to load from separated files first")
                    self._load_from_separated_files()
                    
                    # 重新收集数据
                    all_data = []
                    for key, data_item in self._id_2_data.items():
                        try:
                            if hasattr(data_item, 'to_dict'):
                                all_data.append(data_item.to_dict())
                            elif hasattr(data_item, '_data'):
                                all_data.append(data_item._data)
                            elif isinstance(data_item, dict):
                                all_data.append(data_item)
                        except Exception as e:
                            log.warning(f"Failed to convert data item {key}: {e}")
                            continue

                # 如果仍然没有数据，不要清空文件，直接返回
                if not all_data:
                    log.warning(f"No data to save for merged file: {merge_file}")
                    return

                # 先写入临时文件
                with open(temp_file, "w", encoding="utf-8") as f:
                    yaml.dump(all_data, f, allow_unicode=True, indent=2)
                    f.flush()  # 确保数据写入磁盘

                # 使用原子替换操作
                # Windows 上 replace() 是原子的，但可能需要重试
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        temp_file.replace(merge_file)
                        log.debug(f"Saved merged data to: {merge_file} ({len(all_data)} items)")
                        break
                    except PermissionError as e:
                        if attempt < max_retries - 1:
                            log.warning(f"Retry {attempt + 1}/{max_retries} for replacing merge file: {e}")
                            import time
                            time.sleep(0.1)  # 等待 100ms 后重试
                        else:
                            raise

            except Exception as e:
                log.error(f"Failed to save merged file: {e}")
                # 清理临时文件
                self._cleanup_temp_file(temp_file)
                raise
            finally:
                # 确保清理临时文件（如果还存在）
                self._cleanup_temp_file(temp_file)

    def _cleanup_temp_file(self, temp_file: Path) -> None:
        """
        清理临时文件

        Args:
            temp_file: 临时文件路径
        """
        try:
            if temp_file.exists():
                temp_file.unlink()
                log.debug(f"Cleaned up temporary file: {temp_file}")
        except OSError as e:
            log.warning(f"Failed to cleanup temporary file {temp_file}: {e}")
