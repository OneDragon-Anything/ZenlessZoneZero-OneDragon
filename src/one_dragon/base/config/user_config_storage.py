import shutil
from datetime import datetime
from pathlib import Path
from threading import Lock

from sqlalchemy.orm import Session

from one_dragon.base.config.sqlite_operator import (
    ConfigContent,
    SqliteConnection,
    SqliteRepository,
)


class UserConfigStorage(SqliteRepository):
    """用户配置存储，直接访问 config_content 表。"""

    def __init__(self) -> None:
        self._lock: Lock = Lock()
        super().__init__(SqliteConnection())

    def init(self) -> None:
        """初始化用户配置统一使用的 SQLite 存储。"""
        with self._lock:
            self.connection.init_db()

    def close(self, checkpoint: bool = True) -> None:
        """关闭用户配置 SQLite 存储。"""
        with self._lock:
            self.connection.close_db(checkpoint=checkpoint)

    def load_text(self, key: str, backup_key: str | None = None) -> str | None:
        """读取配置文本；必要时从备份 key 迁移。"""
        text = self.read_text(key)
        if text is not None or backup_key is None:
            return text
        return self.move_key(backup_key, key)

    def read_text(self, key: str) -> str | None:
        """读取配置文本。"""
        return self.read(lambda session: self._read_text(session, key))

    def save_text(self, key: str, text: str) -> None:
        """保存配置文本。"""

        def save(session: Session) -> None:
            record = ConfigContent(path=key, content=text, timestamp=datetime.now())
            session.merge(record)

        self.write(f"保存配置失败 {key}", save)

    def delete_text(self, key: str) -> None:
        """删除配置文本。"""

        def delete(session: Session) -> None:
            record = session.get(ConfigContent, key)
            if record is not None:
                session.delete(record)

        self.write(f"删除配置失败 {key}", delete)

    def exists(self, key: str) -> bool:
        """判断配置是否已持久化。"""
        return self.read(lambda session: session.get(ConfigContent, key) is not None)

    def move_key(self, old_key: str, new_key: str) -> str | None:
        """迁移配置 key，并返回迁移内容。"""

        def move(session: Session) -> str | None:
            record = session.get(ConfigContent, old_key)
            if record is None:
                return None

            content = record.content
            session.merge(ConfigContent(path=new_key, content=content, timestamp=datetime.now()))
            session.delete(record)
            return content

        return self.write(f"迁移配置失败 {old_key} -> {new_key}", move)

    def prepare_legacy_yaml_alias(self, key: str, current_path: Path, legacy_path: Path) -> None:
        """为旧 YAML 路径准备一次兼容别名。"""
        if self.exists(key) or current_path.exists() or not legacy_path.exists():
            return
        current_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_path, current_path)

    def _read_text(self, session: Session, key: str) -> str | None:
        """读取指定 key 的文本。"""
        record = session.get(ConfigContent, key)
        return record.content if record is not None else None
