import json
from pathlib import Path
from typing import Optional

from one_dragon.base.config.sqlite_operator import SQLITE_OPERATOR
from one_dragon.utils import os_utils


class UserConfig:
    """
    使用 SQLite 存储的用户配置。
    用户配置无需考虑sample，所有默认值由代码定义。
    """

    def __init__(
        self,
        module_name: str,
        backup_module_name: Optional[str] = None,
        instance_idx: Optional[int] = None,
        sub_dir: list[str] | None = None,
        is_mock: bool = False,
    ):
        self.instance_idx: Optional[int] = instance_idx
        self.sub_dir: list[str] | None = sub_dir
        self.module_name: str = module_name
        self.backup_module_name: Optional[str] = backup_module_name
        self.is_mock: bool = is_mock

        # 内存数据
        self.data: dict = {}
        self.key = self._get_key(self.module_name)

        # mock 模式不做任何 IO -> 直接返回，避免后续逻辑与副作用
        if self.is_mock:
            return

        text = SQLITE_OPERATOR.get(self.key)

        if text is None:
            text = self._read_from_backup()

        if text is None:
            text = self._read_from_file()

        if text is not None:
            self.data = self._parse_text_to_dict(text)

    def get(self, prop: str, value=None):
        return (self.data or {}).get(prop, value)

    def save(self):
        if self.is_mock or self.key is None:
            return
        try:
            text = self._to_json_text(self.data or {})
            SQLITE_OPERATOR.save(self.key, text)
        except Exception:
            pass

    def update(self, key: str, value, save: bool = True):
        if self.data is None:
            self.data = {}
        if key in self.data and not isinstance(value, list) and self.data[key] == value:
            return
        self.data[key] = value
        if save:
            self.save()

    def delete(self):
        if self.key is None or self.is_mock:
            return
        SQLITE_OPERATOR.delete(self.key)

    def get_prop_adapter(self, prop: str,
                         getter_convert: Optional[str] = None,
                         setter_convert: Optional[str] = None):
        """
        获取一个配置适配器
        :param prop: 配置字段
        :param getter_convert: 获取时的转换器
        :param setter_convert: 设置时的转换器
        :return:
        """
        from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter
        return YamlConfigAdapter(
            config=self,
            field=prop,
            getter_convert=getter_convert,
            setter_convert=setter_convert
        )

    def _get_key(self, module_name) -> Optional[str]:
        if self.is_mock:
            return None
        path = module_name
        if self.sub_dir:
            path = '/'.join(self.sub_dir + [module_name])
        if self.instance_idx is not None:
            path = f'{self.instance_idx%2:d}/{path}'
        return path

    def _get_yaml_path(self) -> Path | None:
        if self.is_mock:
            return None

        sub_dir = ['config']
        if self.instance_idx is not None:
            sub_dir.append(f'{self.instance_idx:02d}')
        if self.sub_dir is not None:
            sub_dir = sub_dir + self.sub_dir

        dir_path = Path(os_utils.get_work_dir()) / Path(*sub_dir)
        yml = f'{self.module_name}.yml'
        return dir_path / yml

    def _read_from_backup(self) -> Optional[str]:
        if self.backup_module_name:
            # 先尝试从数据库读取备份配置
            backup_key = self._get_key(self.backup_module_name)
            backup_text = SQLITE_OPERATOR.get(backup_key)
            if backup_text is not None:
                # 备份配置存在于数据库中，将其迁移到当前配置
                SQLITE_OPERATOR.save(self.key, backup_text)
                SQLITE_OPERATOR.delete(backup_key)
                return backup_text
        return None

    def _read_from_file(self) -> Optional[str]:
        file_path = self._get_yaml_path()

        if not file_path or not file_path.exists():
            return None

        try:
            raw = file_path.read_text(encoding='utf-8')
            try:
                import yaml
                data = yaml.safe_load(raw) or {}
            except Exception:
                pass
            text = self._to_json_text(data)
            SQLITE_OPERATOR.save(self.key, text)
            # 迁移完成后删除原文件并清理空目录
            self._cleanup_source_file_and_dirs(file_path)
            return text
        except Exception:
            return None

    def _cleanup_source_file_and_dirs(self, path: Path):
        """删除源 yml 文件，并自下而上清理空目录直到 config 根目录。"""
        # try:
        #     if not path:
        #         return
        #     # 跳过 sample 文件
        #     if str(path).endswith('.sample.yml'):
        #         return
        #     if path.exists():
        #         path.unlink()
        # except Exception:
        #     # 删除文件失败不阻塞
        #     pass

        # try:
        #     config_root = Path(os_utils.get_path_under_work_dir('config')).resolve()
        #     # 自下而上清理空目录，但不越过 config 根
        #     cur = Path(path).parent
        #     while True:
        #         cur_res = cur.resolve()
        #         if cur_res == config_root:
        #             break
        #         try:
        #             # 仅当目录存在且为空时删除
        #             if cur.exists() and not any(cur.iterdir()):
        #                 cur.rmdir()
        #             else:
        #                 break
        #         except Exception:
        #             break
        #         cur = cur.parent
        # except Exception:
        #     pass
        pass

    def _to_json_text(self, obj) -> str:
        """将对象序列化为 JSON 文本"""
        # 处理少量可能出现的非常规类型
        def _default(o):
            try:
                if isinstance(o, set):
                    return list(o)
                from pathlib import Path as _P
                if isinstance(o, _P):
                    return str(o)
            except Exception:
                pass
            try:
                return str(o)
            except Exception:
                return None

        try:
            return json.dumps(
                obj,
                ensure_ascii=False,
                separators=(',', ':'),
                default=_default,
            )
        except Exception:
            return '{}'

    def _parse_text_to_dict(self, text: str) -> dict:
        """将 sqlite 中的文本解析为 dict。"""
        if not text or not str(text).strip():
            return {}
        try:
            return json.loads(text) or {}
        except Exception:
            return {}
