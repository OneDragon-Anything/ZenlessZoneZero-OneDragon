import json
from pathlib import Path
from typing import Any, ClassVar

from one_dragon.base.config.user_config_storage import UserConfigStorage
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class UserConfig:
    """
    使用 SQLite 存储的用户配置。
    用户配置无需考虑sample，所有默认值由代码定义。
    """

    _storage: ClassVar[UserConfigStorage] = UserConfigStorage()

    @classmethod
    def init_config_storage(cls) -> None:
        """初始化用户配置统一使用的 SQLite 存储。"""
        UserConfig._storage.init()

    @classmethod
    def close_config_storage(cls, checkpoint: bool = True) -> None:
        """关闭用户配置 SQLite 存储。"""
        UserConfig._storage.close(checkpoint=checkpoint)

    @classmethod
    def prepare_legacy_yaml_alias(cls, key: str, current_path: Path, legacy_path: Path) -> None:
        """为旧 YAML 路径准备一次兼容别名。"""
        UserConfig._storage.prepare_legacy_yaml_alias(key, current_path, legacy_path)

    def __init__(
        self,
        module_name: str,
        backup_module_name: str | None = None,
        instance_idx: int | None = None,
        sub_dir: list[str] | None = None,
        is_mock: bool = False,
    ) -> None:
        self.instance_idx: int | None = instance_idx
        self.sub_dir: list[str] | None = sub_dir
        self.module_name: str = module_name
        self.backup_module_name: str | None = backup_module_name
        self.is_mock: bool = is_mock

        # 内存数据
        self.data: dict[str, Any] = {}
        self.key: str | None = self._get_key(self.module_name)

        # mock 模式不做任何 IO -> 直接返回，避免后续逻辑与副作用
        if self.is_mock:
            return

        if self.key is None:
            return

        text = UserConfig._storage.load_text(self.key, self._get_backup_key())

        if text is None:
            text = self._read_from_backup_file()

        if text is None:
            text = self._read_from_current_file()

        if text is not None:
            self.data = self._parse_text_to_dict(text)

    def get(self, prop: str, value: Any = None) -> Any:
        return (self.data or {}).get(prop, value)

    def save(self) -> None:
        if self.is_mock or self.key is None:
            return
        text = self._to_json_text(self.data or {})
        UserConfig._storage.save_text(self.key, text)

    def update(self, key: str, value: Any, save: bool = True) -> None:
        if self.data is None:
            self.data = {}
        if key in self.data and not isinstance(value, list) and self.data[key] == value:
            return
        self.data[key] = value
        if save:
            self.save()

    def delete(self) -> None:
        if self.key is None or self.is_mock:
            return
        UserConfig._storage.delete_text(self.key)

    def get_prop_adapter(
        self,
        prop: str,
        getter_convert: str | None = None,
        setter_convert: str | None = None,
    ) -> Any:
        """
        获取一个配置适配器
        :param prop: 配置字段
        :param getter_convert: 获取时的转换器
        :param setter_convert: 设置时的转换器
        :return:
        """
        from one_dragon.base.config.config_adapter import ConfigAdapter
        return ConfigAdapter(
            config=self,
            field=prop,
            getter_convert=getter_convert,
            setter_convert=setter_convert
        )

    def _get_key(self, module_name: str) -> str | None:
        if self.is_mock:
            return None
        path = module_name
        if self.sub_dir:
            path = '/'.join(self.sub_dir + [module_name])
        if self.instance_idx is not None:
            path = f'{self.instance_idx % 10}/{path}'
        return path

    @property
    def is_file_exists(self) -> bool:
        """
        配置是否已经持久化。
        """
        if self.is_mock or self.key is None:
            return False
        return UserConfig._storage.exists(self.key)

    def _get_yaml_path(self, module_name: str | None = None) -> Path | None:
        if self.is_mock:
            return None

        sub_dir = ['config']
        if self.instance_idx is not None:
            sub_dir.append(f'{self.instance_idx:02d}')
        if self.sub_dir is not None:
            sub_dir = sub_dir + self.sub_dir

        dir_path = Path(os_utils.get_work_dir()) / Path(*sub_dir)
        yml = f'{module_name or self.module_name}.yml'
        return dir_path / yml

    def _get_backup_key(self) -> str | None:
        """获取备份配置 key。"""
        if not self.backup_module_name:
            return None
        return self._get_key(self.backup_module_name)

    def _read_from_backup_file(self) -> str | None:
        """从旧 YAML 备份文件迁移。"""
        if self.backup_module_name:
            backup_file_path = self._get_yaml_path(self.backup_module_name)
            if backup_file_path and backup_file_path.exists():
                text = self._read_yaml_file_to_sqlite(backup_file_path)
                if text is not None:
                    return text
        return None

    def _read_from_current_file(self) -> str | None:
        """从当前旧 YAML 文件迁移。"""
        file_path = self._get_yaml_path()

        if not file_path or not file_path.exists():
            return None

        return self._read_yaml_file_to_sqlite(file_path)

    def _read_yaml_file_to_sqlite(self, file_path: Path) -> str | None:
        """读取 YAML 文件并迁移到 SQLite。"""
        if self.key is None:
            return None

        try:
            raw = file_path.read_text(encoding='utf-8')
        except Exception:
            log.warning("读取配置文件失败 %s", file_path, exc_info=True)
            return None

        data = {}
        try:
            import yaml
            data = yaml.safe_load(raw) or {}
        except Exception:
            log.warning("解析配置文件失败 %s", file_path, exc_info=True)

        try:
            text = self._to_json_text(data)
            UserConfig._storage.save_text(self.key, text)
        except Exception:
            log.error("配置迁移写入数据库失败 %s", file_path, exc_info=True)
            return None

        # 迁移完成后删除原文件并清理空目录
        self._cleanup_source_file_and_dirs(file_path)
        return text

    def _cleanup_source_file_and_dirs(self, path: Path) -> None:
        """删除源 yml 文件，并自下而上清理空目录直到 config 根目录。"""
        if not path:
            return

        if str(path).endswith('.sample.yml'):
            return

        try:
            if path.exists():
                path.unlink()
        except Exception:
            log.warning("删除配置文件失败 %s", path, exc_info=True)
            return

        try:
            config_root = (Path(os_utils.get_work_dir()) / 'config').resolve()
        except Exception:
            return

        cur = path.parent
        while True:
            try:
                cur_res = cur.resolve()
            except Exception:
                break

            if cur_res == config_root:
                break

            try:
                if cur.exists() and cur.is_dir() and not any(cur.iterdir()):
                    cur.rmdir()
                    cur = cur.parent
                    continue
            except Exception:
                log.debug("清理配置目录失败 %s", cur, exc_info=True)
                break
            break

    def _to_json_text(self, obj: Any) -> str:
        """将对象序列化为 JSON 文本"""
        # 处理少量可能出现的非常规类型
        def _default(o: Any) -> Any:
            try:
                if isinstance(o, set):
                    return list(o)
                if isinstance(o, Path):
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

    def _parse_text_to_dict(self, text: str) -> dict[str, Any]:
        """将 sqlite 中的文本解析为 dict。"""
        if not text or not str(text).strip():
            return {}
        try:
            return json.loads(text) or {}
        except Exception:
            return {}
