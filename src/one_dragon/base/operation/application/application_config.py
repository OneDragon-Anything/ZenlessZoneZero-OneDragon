import os
import shutil

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.utils import os_utils


class ApplicationConfig(YamlOperator):
    def __init__(self, app_id: str, instance_idx: int, group_id: str):
        """
        应用配置，保存在 config/{instance_idx}/{group_id}/{app_id}.yml 文件中
        如果应用需要在特殊的应用组中有单独的配置，则传入具体的应用组ID(group_id)
        否则使用默认的 group_id='one_dragon' 即可

        Args:
            app_id: 应用ID
            instance_idx: 实例下标
            group_id: 应用组ID
        """
        file_path = os.path.join(
            os_utils.get_path_under_work_dir("config", ('%02d' % instance_idx), group_id),
            f"{app_id}.yml",
        )

        # 需要从没有group_id的版本迁移过来 预计 2026-09-21 可以删除这段代码
        old_path = os.path.join(
            os_utils.get_path_under_work_dir("config", ('%02d' % instance_idx)),
            f"{app_id}.yml",
        )
        if not os.path.exists(file_path) and os.path.exists(old_path):
            shutil.copy2(old_path, file_path)

        YamlOperator.__init__(self, file_path=file_path)
