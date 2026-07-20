from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.config.one_dragon_app_config import OneDragonAppConfig
from one_dragon.base.operation.application.application_const import DEFAULT_GROUP_ID
from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
    ApplicationGroupConfigItem,
)

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class ApplicationGroupManager:

    def __init__(self, ctx: OneDragonContext):
        self.ctx: OneDragonContext = ctx

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
        return [DEFAULT_GROUP_ID]

    def get_group_config(self, instance_idx: int, group_id: str) -> ApplicationGroupConfig | None:
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
            if group_id == DEFAULT_GROUP_ID:
                config = self._init_one_dragon_group_config(instance_idx=instance_idx)
            else:
                config = ApplicationGroupConfig(instance_idx=instance_idx, group_id=group_id)
            self._config_cache[key] = config

        for app in config.app_list:
            app.app_name = self.ctx.run_context.get_application_name(app_id=app.app_id)

        return config

    def set_default_apps(self, app_id_list: list[str]) -> None:
        """
        -
        Args:
            app_id_list: 包含的应用ID列表
        """
        self._default_app_id_list = app_id_list

    def set_one_dragon_app_enable(
        self,
        config: ApplicationGroupConfig,
        app_id: str,
        enabled: bool,
    ) -> bool:
        """更新一条龙应用状态，非默认组应用禁用后从配置中移除。

        Returns:
            是否从一条龙配置中移除了应用。
        """
        if not enabled and app_id not in self._default_app_id_list:
            config.remove_app(app_id)
            return True

        config.set_app_enable(app_id, enabled)
        return False

    def get_one_dragon_group_config(self, instance_idx: int) -> ApplicationGroupConfig:
        """
        获取默认应用组的配置

        Args:
            instance_idx: 账号实例下标
        """
        return self.get_group_config(instance_idx=instance_idx, group_id=DEFAULT_GROUP_ID)

    def _init_one_dragon_group_config(self, instance_idx: int) -> ApplicationGroupConfig:
        """
        获取默认应用组的配置

        Args:
            instance_idx: 账号实例下标
        """
        config = ApplicationGroupConfig(instance_idx=instance_idx, group_id=DEFAULT_GROUP_ID)
        need_migration = not config.is_file_exists

        # 默认组应用自动加入，配置中已开启的非默认组应用继续保留显示
        default_app_ids = set(self._default_app_id_list)
        kept_apps: list[ApplicationGroupConfigItem] = []
        migrated_app_ids: list[str] = []
        removed_disabled_app = False
        for item in config._all_apps:
            if item.app_id in default_app_ids:
                kept_apps.append(item)
                continue

            if self.ctx.run_context.is_app_registered(item.app_id):
                if item.enabled:
                    kept_apps.append(item)
                    migrated_app_ids.append(item.app_id)
                else:
                    removed_disabled_app = True
            else:
                kept_apps.append(item)

        if removed_disabled_app:
            config._all_apps = kept_apps
            config.save_app_list()

        app_id_list = [*self._default_app_id_list, *migrated_app_ids]
        config.update_full_app_list(app_id_list)

        # 从旧的配置文件迁移过来 2026-09-21 可删除
        if need_migration:
            old_config = OneDragonAppConfig(instance_idx)
            if old_config.is_file_exists:
                for app_id in old_config.app_run_list:
                    config.set_app_enable(app_id, True)

                config.set_app_order(old_config.app_order)

        return config

    def clear_config_cache(self) -> None:
        """清除配置缓存

        在刷新应用注册时调用，使配置重新加载。
        """
        self._config_cache.clear()
