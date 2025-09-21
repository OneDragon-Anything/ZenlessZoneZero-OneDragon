import os

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.utils import os_utils


class ApplicationGroupConfigItem:

    def __init__(self, app_id: str, enabled: bool):
        """
        应用组配置项

        Args:
            app_id: 应用ID
            enabled: 是否启用
        """
        self.app_id: str = app_id
        self.enabled: bool = enabled


class ApplicationGroupConfig(YamlOperator):

    def __init__(self, instance_idx: int, group_id: str):
        """
        应用组配置，保存在 config/{instance_idx}/{group_id}/_group.yml 文件中

        Args:
            instance_idx: 账号实例下标
            group_id: 应用组ID
        """
        file_path = os.path.join(
            os_utils.get_path_under_work_dir(
                "config", ("%02d" % instance_idx), group_id
            ),
            "_group.yml",
        )

        self.group_id: str = group_id
        YamlOperator.__init__(self, file_path=file_path)

    @property
    def app_list(self) -> list[ApplicationGroupConfigItem]:
        dict_list = self.get("app_list", [])
        return [
            ApplicationGroupConfigItem(app_id=item["app_id"], enabled=item["enabled"])
            for item in dict_list
        ]

    @app_list.setter
    def app_list(self, value: list[ApplicationGroupConfigItem]):
        self.update("app_list", [
            {
                "app_id": item.app_id,
                "enabled": item.enabled
            }
            for item in value
        ])

    def update_full_app_list(self, app_id_list: list[str]) -> None:
        """
        更新完整的应用ID列表
        只应该被默认组使用 用于填充一条龙默认应用

        Args:
            app_id_list: 应用ID列表
        """
        changed: bool = False

        old_app_list = self.app_list
        new_app_list = [
            app
            for app in old_app_list
            if app.app_id in app_id_list
        ]
        if len(old_app_list) != len(new_app_list):
            changed = True

        existed_app_id_list = [app.app_id for app in new_app_list]
        for app_id in app_id_list:
            if app_id not in existed_app_id_list:
                new_app_list.append(ApplicationGroupConfigItem(app_id=app_id, enabled=False))
                changed = True

        if changed:
            self.app_list = new_app_list
