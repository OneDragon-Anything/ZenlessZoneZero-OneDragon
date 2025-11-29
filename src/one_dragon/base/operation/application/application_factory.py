from abc import ABC

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord


class ApplicationFactory(ABC):
    """
    应用工厂抽象基类。

    负责创建应用实例、应用配置和运行记录的工厂类，提供缓存机制以避免重复创建。
    每个具体应用都需要继承此类并实现其抽象方法来定义应用的创建逻辑。
    """

    def __init__(
        self,
        app_id: str,
        app_name: str,
        need_notify: bool = False,
    ):
        """
        初始化应用工厂。

        Args:
            app_id: 应用唯一标识符，用于区分不同的应用类型
            app_name: 显示用的应用名称
            need_notify: 应用是否需要通知
        """
        self.app_id: str = app_id
        self.app_name: str = app_name
        self.need_notify: bool = need_notify
        self._config_cache: dict[str, ApplicationConfig] = {}
        self._run_record_cache: dict[str, AppRunRecord] = {}

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        """
        创建应用实例。

        由子类实现，用于创建具体的应用实例对象。

        Args:
            instance_idx: 账号实例下标
            group_id: 应用组ID，可将应用分组运行

        Returns:
            Application: 创建的应用实例对象
        """
        raise Exception(f"未提供应用创建方法 {self.app_id}")

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> ApplicationConfig:
        """
        创建配置实例。

        由子类实现，用于创建应用的具体配置对象。

        Args:
            instance_idx: 账号实例下标
            group_id: 应用组ID，不同应用组可以有不同的应用配置

        Returns:
            ApplicationConfig: 创建的配置对象
        """
        raise Exception(f"未提供应用配置创建方法 {self.app_id}")

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        """
        创建运行记录实例。

        由子类实现，用于创建应用的运行记录对象，用于记录应用的运行状态和历史。

        Args:
            instance_idx: 账号实例下标

        Returns:
            AppRunRecord: 创建的运行记录对象
        """
        raise Exception(f"未提供应用运行记录创建方法 {self.app_id}")

    def get_config(
        self, instance_idx: int, group_id: str
    ) -> ApplicationConfig:
        """
        获取配置实例。

        使用缓存机制，如果配置已存在则返回缓存的配置，否则创建新的配置并缓存。

        Args:
            instance_idx: 账号实例下标
            group_id: 应用组ID，不同应用组可以有不同的应用配置

        Returns:
            ApplicationConfig: 配置对象

        Raises:
            Exception: 如果子类应用无需配置(即不提供create_config)时，调用本方法会抛出异常
        """
        key = f"{instance_idx}_{group_id}"
        if key in self._config_cache:
            return self._config_cache[key]

        config = self.create_config(instance_idx, group_id)
        if config is not None:
            self._config_cache[key] = config

        return config

    def get_run_record(self, instance_idx: int) -> AppRunRecord:
        """
        获取运行记录实例。

        使用缓存机制，如果运行记录已存在则返回缓存的记录，否则创建新的记录并缓存。

        Args:
            instance_idx: 账号实例下标

        Returns:
            AppRunRecord: 运行记录对象，如果创建失败则返回None

        Raises:
            Exception: 如果子类应用无需配置(即不提供create_run_record)时，调用本方法会抛出异常
        """
        key = f"{instance_idx}"
        if key in self._run_record_cache:
            return self._run_record_cache[key]

        record = self.create_run_record(instance_idx)
        if record is not None:
            self._run_record_cache[key] = record

        return record
