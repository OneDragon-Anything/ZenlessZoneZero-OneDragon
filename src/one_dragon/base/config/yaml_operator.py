import os
import sys
import pickle
import threading
from typing import Optional

import yaml

from one_dragon.utils.log_utils import log

# 全局缓存优化
cached_yaml_data: dict[str, tuple[float, dict]] = {}
cached_file_mtime: dict[str, float] = {}
pickle_cache_paths: dict[str, str] = {}


def get_temp_config_path(file_path: str) -> str:
    """
    优先检查 PyInstaller 运行时的 _MEIPASS/resources 目录下是否有对应文件
    有则返回该路径，否则返回原路径
    """
    if hasattr(sys, '_MEIPASS'):
        try:
            rel_path = os.path.relpath(file_path, os.getcwd())
        except Exception:
            rel_path = os.path.basename(file_path)

        candidates = [
            os.path.join(getattr(sys, '_MEIPASS'), 'resources', rel_path),
            # 兼容旧行为：仅按文件名在 _MEIPASS/config 下查找
            os.path.join(getattr(sys, '_MEIPASS'), 'config', os.path.basename(file_path)),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
    return file_path

def read_cache_or_load(file_path: str):
    """
    优先级: 内存缓存 > Pickle缓存 > YAML文件
    """
    # 统一走 MEI 路径映射，兼容预加载等直接传入相对路径的场景
    file_path = get_temp_config_path(file_path)

    # 0. 快速路径：检查是否已有完全匹配的缓存
    cached = cached_yaml_data.get(file_path)
    try:
        last_modify = os.path.getmtime(file_path)
    except OSError:
        return cached[1] if cached else {}

    if cached is not None and cached[0] >= last_modify:
        return cached[1]

    # 2. Pickle
    pickle_cache = file_path + '.yml_cache'
    if os.path.exists(pickle_cache):
        try:
            pickle_mtime = os.path.getmtime(pickle_cache)
            if pickle_mtime >= last_modify:
                with open(pickle_cache, 'rb') as f:
                    data = pickle.load(f)
                cached_yaml_data[file_path] = (last_modify, data)
                return data
        except (OSError, pickle.PickleError):
            try:
                os.remove(pickle_cache)
            except OSError:
                pass

    # 3. YAML
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            log.debug(f"加载yaml: {file_path}")
            data = yaml.safe_load(file)
    except Exception as e:
        log.error(f'YAML加载失败 {file_path}: {e}')
        return {}

    cached_yaml_data[file_path] = (last_modify, data)

    # 生成Pickle缓存
    def save_pickle_cache():
        try:
            with open(pickle_cache, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.utime(pickle_cache, (last_modify, last_modify))
        except Exception:
            pass

    threading.Thread(target=save_pickle_cache, daemon=True).start()

    return data


class YamlOperator:

    def __init__(self, file_path: Optional[str] = None):
        """
        yml文件的操作器
        :param file_path: yml文件的路径。不传入时认为是mock，用于测试。
        """

        self.file_path: Optional[str] = get_temp_config_path(file_path) if file_path else None
        """yml文件的路径"""

        self.data: dict = {}
        """存放数据的地方"""

        self.__read_from_file()

    def __read_from_file(self) -> None:
        """
        从yml文件中读取数据
        :return:
        """
        if self.file_path is None:
            return
        if not os.path.exists(self.file_path):
            return

        try:
            self.data = read_cache_or_load(self.file_path)
        except Exception:
            log.error(f'文件读取失败 将使用默认值 {self.file_path}', exc_info=True)
            self.data = {}

    def save(self):
        if self.file_path is None:
            return

        with open(self.file_path, 'w', encoding='utf-8') as file:
            yaml.dump(self.data, file, allow_unicode=True, sort_keys=False)

    def save_diy(self, text: str):
        """
        按自定义的文本格式
        :param text: 自定义的文本
        :return:
        """
        if self.file_path is None:
            return

        with open(self.file_path, "w", encoding="utf-8") as file:
            file.write(text)

    def get(self, prop: str, value=None):
        return self.data.get(prop, value)

    def update(self, key: str, value, save: bool = True):
        if self.data is None:
            self.data = {}
        if key in self.data and not isinstance(value, list) and self.data[key] == value:
            return
        self.data[key] = value
        if save:
            self.save()

    def delete(self):
        """
        删除配置文件
        :return:
        """
        if self.file_path and os.path.exists(self.file_path):
            os.remove(self.file_path)

    def is_file_exists(self) -> bool:
        """
        配置文件是否存在
        :return:
        """
        return self.file_path is not None and os.path.exists(self.file_path)
