from __future__ import annotations

from typing import Optional
from typing import TYPE_CHECKING

import os
from one_dragon.utils import os_utils
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
        config_dir = os_utils.get_path_under_work_dir("config", ("%02d" % instance_idx))
        if not os.path.exists(config_dir):
            return [DEFAULT_GROUP_ID]

        group_ids = []
        for item in os.listdir(config_dir):
            if item == 'app_run_record':
                continue
            item_path = os.path.join(config_dir, item)
            if os.path.isdir(item_path):
                group_ids.append(item)

        # 确保默认组存在
        if DEFAULT_GROUP_ID not in group_ids:
            group_ids.append(DEFAULT_GROUP_ID)

        return group_ids

    def create_group(self, instance_idx: int, group_name: str) -> bool:
        """
        创建新的应用组

        Args:
            instance_idx: 账号实例下标
            group_name: 组名称（将作为目录名）

        Returns:
            bool: 是否创建成功
        """
        if not group_name or group_name == DEFAULT_GROUP_ID:
            return False

        config_dir = os_utils.get_path_under_work_dir("config", ("%02d" % instance_idx), group_name)
        config_file_path = os.path.join(config_dir, "_group.yml")
        if os.path.exists(config_file_path):
            from one_dragon.utils.log_utils import log
            log.error(f"创建分组失败: 配置文件已存在 {config_file_path}")
            return False  # 已存在

        try:
            os.makedirs(config_dir, exist_ok=True)
            # 创建 _group.yml 文件，复制默认组的应用列表但全部禁用
            config = ApplicationGroupConfig(instance_idx=instance_idx, group_id=group_name)
            default_config = self.get_group_config(instance_idx=instance_idx, group_id=DEFAULT_GROUP_ID)
            for app in default_config.app_list:
                config.app_list.append(ApplicationGroupConfigItem(app_id=app.app_id, enabled=False))
            config.save_app_list()
            # 清除缓存
            key = f'{instance_idx}_{group_name}'
            if key in self._config_cache:
                del self._config_cache[key]
            return True
        except Exception:
            from one_dragon.utils.log_utils import log
            log.error("创建分组失败", exc_info=True)
            return False

    def delete_group(self, instance_idx: int, group_id: str) -> bool:
        """
        删除应用组

        Args:
            instance_idx: 账号实例下标
            group_id: 组ID

        Returns:
            bool: 是否删除成功
        """
        if group_id == DEFAULT_GROUP_ID:
            return False  # 不允许删除默认组

        config_dir = os_utils.get_path_under_work_dir("config", ("%02d" % instance_idx), group_id)
        if not os.path.exists(config_dir):
            return False

        try:
            import shutil
            shutil.rmtree(config_dir)
            # 清除缓存
            key = f'{instance_idx}_{group_id}'
            if key in self._config_cache:
                del self._config_cache[key]
            return True
        except Exception:
            from one_dragon.utils.log_utils import log
            log.error("删除分组失败", exc_info=True)
            return False

    def rename_group(self, instance_idx: int, old_group_id: str, new_group_name: str) -> bool:
        """
        重命名应用组

        Args:
            instance_idx: 账号实例下标
            old_group_id: 旧组ID
            new_group_name: 新组名称

        Returns:
            bool: 是否重命名成功
        """
        if old_group_id == DEFAULT_GROUP_ID or not new_group_name or new_group_name == DEFAULT_GROUP_ID:
            return False

        old_dir = os_utils.get_path_under_work_dir("config", ("%02d" % instance_idx), old_group_id)
        new_dir = os_utils.get_path_under_work_dir("config", ("%02d" % instance_idx), new_group_name)

        if not os.path.exists(old_dir) or os.path.exists(new_dir):
            return False

        try:
            os.rename(old_dir, new_dir)
            # 清除旧缓存
            old_key = f'{instance_idx}_{old_group_id}'
            if old_key in self._config_cache:
                del self._config_cache[old_key]
            # 清除新缓存（如果存在）
            new_key = f'{instance_idx}_{new_group_name}'
            if new_key in self._config_cache:
                del self._config_cache[new_key]
            return True
        except Exception:
            return False

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

        return config