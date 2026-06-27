from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.config.one_dragon_app_config import OneDragonAppConfig
from one_dragon.base.operation.application.application_const import DEFAULT_GROUP_ID
from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
)
from one_dragon.utils.log_utils import log

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
        config.update_full_app_list(self._default_app_id_list)

        # 从旧的配置文件迁移过来 2026-09-21 可删除
        if need_migration:
            old_config = OneDragonAppConfig(instance_idx)
            if old_config.is_file_exists:
                for app_id in old_config.app_run_list:
                    config.set_app_enable(app_id, True)

                config.set_app_order(old_config.app_order)

        # TODO: 2026-08-31 后可安全移除本检测与迁移逻辑
        self._migrate_daily_signin(config, instance_idx)

        return config

    def _migrate_daily_signin(self, config: ApplicationGroupConfig, instance_idx: int) -> None:
        """
        老用户迁移合并3个签到到每日签到应用。
        检查如果老用户在一条龙里启用了老签到应用之一，那么：
        1. 自动启用 daily_signin，并保持原本的位置顺序。
        2. 将选中的老签到写入 daily_signin 的 selected_sign。
        3. 将老签到从一条龙配置列表中彻底删除，净化配置文件。
        """
        old_sign_ids = ['hou_hou_bakery', 'trigrams_collection', 'scratch_card']
        enabled_old_app_id: str | None = None

        # 检查是否有老签到是启用的
        for item in config._all_apps:
            if item.app_id in old_sign_ids and item.enabled:
                enabled_old_app_id = item.app_id
                break

        if enabled_old_app_id is None:
            return

        log.info(f"检测到实例 {instance_idx} 的老签到应用 {enabled_old_app_id} 处于启用状态，开始迁移至每日签到...")

        # 寻找在 _all_apps 中的位置
        daily_signin_item = None
        daily_signin_idx = -1
        first_old_idx = -1

        for i, item in enumerate(config._all_apps):
            if item.app_id == 'daily_signin':
                daily_signin_item = item
                daily_signin_idx = i
            elif item.app_id in old_sign_ids and first_old_idx == -1:
                first_old_idx = i

        # 1. 调整 daily_signin 的位置（如果适用）并设为启用
        if daily_signin_item is not None and first_old_idx != -1 and daily_signin_idx > first_old_idx:
            config._all_apps.pop(daily_signin_idx)
            config._all_apps.insert(first_old_idx, daily_signin_item)

        if daily_signin_item is not None:
            daily_signin_item.enabled = True

        # 2. 写入 daily_signin 的配置
        try:
            from one_dragon.base.operation.application.application_config import (
                ApplicationConfig,
            )
            daily_signin_config = ApplicationConfig('daily_signin', instance_idx, config.group_id)
            daily_signin_config.update('selected_sign', enabled_old_app_id)
            log.info(f"已自动将每日签到的商店配置为: {enabled_old_app_id}")
        except Exception as e:
            log.error(f"每日签到配置迁移失败: {e}", exc_info=True)

        # 3. 将所有老应用彻底从列表配置中删除，净化配置文件
        config._all_apps = [item for item in config._all_apps if item.app_id not in old_sign_ids]

        # 4. 重新生成 config.app_list 以确保保存和内存中的状态都具有正确的位置顺序
        registered_set = set(self._default_app_id_list)
        config.app_list = [item for item in config._all_apps if item.app_id in registered_set]

        # 5. 保存应用列表
        config.save_app_list()

        log.info(f"实例 {instance_idx} 签到迁移完成")

    def clear_config_cache(self) -> None:
        """清除配置缓存

        在刷新应用注册时调用，使配置重新加载。
        """
        self._config_cache.clear()
