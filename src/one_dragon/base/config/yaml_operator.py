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

def preload_common_configs():
    """
    预加载常用配置文件到内存
    """
    common_configs = [
        'config/zzz_one_dragon.yml',
        'config/01/game.yml',
        'config/01/battle_assistant.yml',
        'config/01/agent_outfit.yml',
        'config/01/game_account.yml',
        'config/01/one_dragon_app.yml',
        'config/01/push.yml',
        'config/01/screenshot_helper.yml',
        'config/02/game.yml',
        'config/02/agent_outfit.yml',
        'config/03/game.yml',
    ]
    
    def preload_worker():
        for config_file in common_configs:
            try:
                if os.path.exists(config_file):
                    read_cache_or_load(config_file)
            except Exception:
                pass
    
    threading.Thread(target=preload_worker, daemon=True).start()


def clear_cache_if_needed():
    """
    智能内存管理
    """
    if len(cached_yaml_data) > 100:
        items = list(cached_yaml_data.items())
        cached_yaml_data.clear()
        cached_file_mtime.clear()
        
        for k, v in items[-50:]:
            cached_yaml_data[k] = v


def get_temp_config_path(file_path: str) -> str:
    """
    优先检查PyInstaller运行时的_MEIPASS目录下是否有对应的yml文件
    有则返回该路径，否则返回原路径
    """
    if hasattr(sys, '_MEIPASS'):
        mei_path = os.path.join(getattr(sys, '_MEIPASS'), 'config', os.path.basename(file_path))
        if os.path.exists(mei_path):
            return mei_path
    return file_path

def read_cache_or_load(file_path: str):
    """
    优先级: 内存缓存 > Pickle缓存 > YAML文件
    """
    # 0. 快速路径：检查是否已有完全匹配的缓存
    cached = cached_yaml_data.get(file_path)
    try:
        last_modify = os.path.getmtime(file_path)
    except OSError:
        return cached[1] if cached else {}

    if cached is not None and cached[0] >= last_modify:
        return cached[1]

    # 2. Pickle
    pickle_cache = file_path + '.ui_cache'
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

    @property
    def is_file_exists(self) -> bool:
        """
        配置文件是否存在
        :return:
        """
        return bool(self.file_path) and os.path.exists(self.file_path)
