from pathlib import Path

from one_dragon.base.config.user_config import UserConfig
from one_dragon.utils import os_utils


class ApplicationConfig(UserConfig):
    def __init__(self, app_id: str, instance_idx: int, group_id: str):
        """
        应用配置，最终保存在 SQLite 中。
        旧版 config/{instance_idx}/{group_id}/{app_id}.yml 会在首次读取时迁移。
        如果应用需要在特殊的应用组中有单独的配置，则传入具体的应用组ID(group_id)
        否则使用默认的 group_id='one_dragon' 即可

        Args:
            app_id: 应用ID
            instance_idx: 实例下标
            group_id: 应用组ID
        """
        config_dir = Path(os_utils.get_work_dir()) / 'config' / f'{instance_idx:02d}'
        file_path = config_dir / group_id / f'{app_id}.yml'

        # 需要从没有group_id的版本迁移过来 预计 2026-09-21 可以删除这段代码
        old_path = config_dir / f'{app_id}.yml'
        sqlite_key = f'{instance_idx % 10}/{group_id}/{app_id}'
        UserConfig.prepare_legacy_yaml_alias(sqlite_key, file_path, old_path)

        UserConfig.__init__(self, app_id, instance_idx=instance_idx, sub_dir=[group_id])
