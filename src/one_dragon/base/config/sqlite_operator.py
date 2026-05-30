from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, TypeVar

from sqlalchemy import DateTime, String, Text, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    scoped_session,
    sessionmaker,
)

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log

T = TypeVar("T")


class Base(DeclarativeBase):
    pass


class ConfigContent(Base):
    """
    单表kv存储配置内容
    键名为相对于 config 目录的路径，如 '<idx>/...' 的路径。
    """
    __tablename__ = 'config_content'
    __table_args__ = {'extend_existing': True}

    path: Mapped[str] = mapped_column(String(255), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class SqliteConnection:
    """SQLite 连接层，负责 engine/session 生命周期。"""

    def __init__(self, db_name: str = "config.db") -> None:
        self.engine: Engine | None = None
        self.session_factory: sessionmaker | None = None
        self.session: scoped_session | None = None
        self._lock: Lock = Lock()
        self._db_name: str = db_name

    def init_db(self, db_name: str | None = None) -> None:
        """初始化数据库 engine 与 session 工厂。"""
        if self.engine is not None and self.session is not None:
            return

        with self._lock:
            if self.engine is not None and self.session is not None:
                return
            if db_name is not None:
                self._db_name = db_name

            db_dir = Path(os_utils.get_path_under_work_dir('config'))
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = (db_dir / self._db_name).resolve()
            self.engine = create_engine(
                f'sqlite:///{db_path}',
                connect_args={"check_same_thread": False}
            )

            # 使用事件监听器，确保每个连接都开启 WAL 模式
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
                """为每个 SQLite 连接设置 PRAGMA。"""
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA busy_timeout = 5000;")
                    cursor.execute("PRAGMA foreign_keys=ON;")
                finally:
                    cursor.close()

            Base.metadata.create_all(self.engine)
            self.session_factory = sessionmaker(bind=self.engine)
            self.session = scoped_session(self.session_factory)

    def ensure_init(self) -> None:
        """确保数据库已经初始化。"""
        if self.session is None or self.engine is None:
            self.init_db(self._db_name)

    def get_session(self) -> scoped_session:
        """获取 scoped_session。"""
        self.ensure_init()
        session_factory = self.session
        if session_factory is None:
            raise RuntimeError("数据库未初始化")
        return session_factory

    def close_db(self, checkpoint: bool = True) -> None:
        """移除 sessions，可选 WAL checkpoint，然后 dispose engine。"""
        with self._lock:
            if self.session is not None:
                try:
                    self.session.remove()
                finally:
                    self.session = None
                    self.session_factory = None

            if checkpoint and self.engine is not None:
                try:
                    with self.engine.connect() as conn:
                        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
                except Exception:
                    log.exception("WAL checkpoint failed")

            if self.engine is not None:
                try:
                    self.engine.dispose()
                finally:
                    self.engine = None


class SqliteRepository:
    """SQLite 数据访问基类，统一管理 session 生命周期。"""

    def __init__(self, connection: SqliteConnection) -> None:
        self.connection: SqliteConnection = connection

    def read(self, handler: Callable[[Session], T]) -> T:
        """执行一次读操作。"""
        with self._session_scope() as session:
            return handler(session)

    def write(self, error_message: str, handler: Callable[[Session], T]) -> T:
        """执行一次写操作。"""
        with self._transaction_scope(error_message) as session:
            return handler(session)

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        """创建一次读操作 session。"""
        session_factory = self.connection.get_session()
        session = session_factory()
        try:
            yield session
        finally:
            session_factory.remove()

    @contextmanager
    def _transaction_scope(self, error_message: str) -> Iterator[Session]:
        """创建一次写操作事务。"""
        session_factory = self.connection.get_session()
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            log.error(error_message, exc_info=True)
            raise
        finally:
            session_factory.remove()
