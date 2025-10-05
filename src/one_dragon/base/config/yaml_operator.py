import atexit
import os
import sys
from typing import Optional

import yaml

from one_dragon.utils.log_utils import log

import concurrent.futures
import threading

mutex = threading.Lock()

_writer_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="yaml-writer"
)

cached_yaml_data: dict[str, tuple[float, dict]] = {}

def write_file_and_flush_cache(file_path: str, data: dict, sync: bool = False):
    cached_yaml_data[file_path] = (0.0, data)
    def write_to_file_and_load_modify_time():
        with mutex:
            with open(file_path, 'w', encoding='utf-8') as file:
                yaml.dump(data, file, allow_unicode=True, sort_keys=False)
            last_modify = os.path.getmtime(file_path)
            cached_yaml_data[file_path] = (last_modify, data)
    if sync:
        write_to_file_and_load_modify_time()
    else:
        _writer_executor.submit(write_to_file_and_load_modify_time)

def get_temp_config_path(file_path: str) -> str:
    """
    优先检查PyInstaller运行时的_MEIPASS目录下是否有对应的yml文件
    有则返回该路径，否则返回原路径
    """
    if hasattr(sys, '_MEIPASS'):
        mei_path = os.path.join(sys._MEIPASS, 'config', os.path.basename(file_path))
        if os.path.exists(mei_path):
            return mei_path
    return file_path

def read_cache_or_load(file_path: str):
    cached = cached_yaml_data.get(file_path)
    last_modify = os.path.getmtime(file_path)
    if cached is not None and cached[0] == last_modify:
        return cached[1]

    with open(file_path, 'r', encoding='utf-8') as file:
        log.debug(f"加载yaml: {file_path}")
        data = yaml.safe_load(file)
        cached_yaml_data[file_path] = (last_modify, data)
        return data

def _writer_executor_atexit():
    _writer_executor.shutdown(wait=True)
atexit.register(_writer_executor_atexit)

class YamlOperator:

    def __init__(self, file_path: Optional[str] = None):
        """
        yml文件的操作器
        :param file_path: yml文件的路径。不传入时认为是mock，用于测试。
        """

        self.file_path: str = get_temp_config_path(file_path) if file_path else None
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
            return

        if self.data is None:
            self.data = {}

    def save(self):
        if self.file_path is None:
            return
        write_file_and_flush_cache(self.file_path, self.data)

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
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    @property
    def is_file_exists(self) -> bool:
        """
        配置文件是否存在
        :return:
        """
        return bool(self.file_path) and os.path.exists(self.file_path)
