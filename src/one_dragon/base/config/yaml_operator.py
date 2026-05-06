import copy
import os
import shutil

import yaml

from one_dragon.utils import yaml_utils
from one_dragon.utils.log_utils import log

cached_yaml_data: dict[str, tuple[float, dict | list]] = {}


def read_cache_or_load(file_path: str) -> dict | list:
    cached = cached_yaml_data.get(file_path)
    last_modify = os.path.getmtime(file_path)
    if cached is not None and cached[0] == last_modify:
        return copy.deepcopy(cached[1])

    with open(file_path, encoding="utf-8") as file:
        log.debug(f"加载yaml: {file_path}")
        data = yaml_utils.safe_load(file)
        if data is None:
            data = {}
        if not isinstance(data, dict | list):
            raise TypeError(f"YAML root must be a dict or list: {file_path}")
        cached_yaml_data[file_path] = (last_modify, data)
        return copy.deepcopy(data)


def invalidate_cache(file_path: str | None) -> None:
    if file_path is None:
        return
    cached_yaml_data.pop(file_path, None)


class YamlOperator:

    def __init__(self, file_path: str | None = None):
        """
        yml文件的操作器
        :param file_path: yml文件的路径。不传入时认为是mock，用于测试。
        """

        self.file_path: str | None = file_path
        """yml文件的路径"""

        self._write_file_path: str | None = file_path
        """实际写入路径 兼容 onedir 下读写路径分离"""

        self._copy_on_write_source_path: str | None = None
        """首次写入前需要复制到写入路径的来源文件"""

        self.data: dict | list = {}
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

    def _ensure_write_path_ready(self) -> bool:
        write_path = self._get_write_path()
        if write_path is None:
            return False

        parent_dir = os.path.dirname(write_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        if self._copy_on_write_source_path is not None and not os.path.exists(write_path):
            shutil.copyfile(self._copy_on_write_source_path, write_path)

        self._copy_on_write_source_path = None
        return True

    def _get_write_path(self) -> str | None:
        if self._copy_on_write_source_path is None:
            return self.file_path if self.file_path is not None else self._write_file_path
        return self._write_file_path if self._write_file_path is not None else self.file_path

    def save(self):
        if not self._ensure_write_path_ready():
            return

        write_path = self._get_write_path()
        if write_path is None:
            return

        with open(write_path, 'w', encoding='utf-8') as file:
            yaml.dump(self.data, file, allow_unicode=True, sort_keys=False)
        invalidate_cache(write_path)

        if self.file_path != write_path:
            self.file_path = write_path
            if hasattr(self, 'old_file_path'):
                self.old_file_path = write_path

    def save_diy(self, text: str):
        """
        按自定义的文本格式
        :param text: 自定义的文本
        :return:
        """
        if not self._ensure_write_path_ready():
            return

        write_path = self._get_write_path()
        if write_path is None:
            return

        with open(write_path, "w", encoding="utf-8") as file:
            file.write(text)
        invalidate_cache(write_path)

        if self.file_path != write_path:
            self.file_path = write_path
            if hasattr(self, 'old_file_path'):
                self.old_file_path = write_path

    def get(self, prop: str, value=None):
        if not isinstance(self.data, dict):
            return value
        return self.data.get(prop, value)

    def update(self, key: str, value, save: bool = True):
        if not isinstance(self.data, dict):
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
        if self.file_path is None:
            return
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
            invalidate_cache(self.file_path)

    @property
    def is_file_exists(self) -> bool:
        """
        配置文件是否存在
        :return:
        """
        return bool(self.file_path) and os.path.exists(self.file_path)
