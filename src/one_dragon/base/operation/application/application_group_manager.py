from typing import Optional

from one_dragon.base.operation.application.application_const import DEFAULT_GROUP_ID
from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
)


class ApplicationGroupManager:

    def __init__(self):
        self._config_cache: dict[str, ApplicationGroupConfig] = {}
        self._default_app_id_list: list[str] = []

    def get_group_list(self, instance_idx: int) -> list[str]:
        """
        获取账号下的分组列表

        Args:
            instance_idx: 账号实例下标

        Returns:
            list[str]: 分组ID列表
        """
        pass

    def get_group_config(self, instance_idx: int, group_id: str) -> Optional[ApplicationGroupConfig]:
        """
        获取分组配置

        Args:
            instance_idx: 账号实例下标
            group_id: 分组ID

        Returns:
            ApplicationGroupConfig: 分组配置
        """
        key = f'{instance_idx}_{group_id}'
        if key in self._config_cache:
            config = self._config_cache[key]
        else:
            config = ApplicationGroupConfig(instance_idx=instance_idx, group_id=group_id)
            self._config_cache[key] = config

        if group_id == DEFAULT_GROUP_ID:
            config.update_full_app_list(self._default_app_id_list)

        return config

    def set_default_apps(self, app_id_list: list[str]) -> None:
        """
        -
        Args:
            app_id_list: 包含的应用ID列表
        """
        self._default_app_id_list = app_id_list
