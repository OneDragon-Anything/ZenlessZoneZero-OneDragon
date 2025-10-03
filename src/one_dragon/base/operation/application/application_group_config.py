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
        self.app_name: str = ''  # 不需要保存 每次注入


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
        YamlOperator.__init__(self, file_path=file_path)

        self.group_id: str = group_id
        self.app_list: list[ApplicationGroupConfigItem] = []

        self._init_app_list()

    def _init_app_list(self) -> None:
        dict_list = self.get("app_list", [])
        for item in dict_list:
            self.app_list.append(
                ApplicationGroupConfigItem(
                    app_id=item.get("app_id", ""),
                    enabled=item.get("enabled", False),
                )
            )

    def save_app_list(self):
        self.update("app_list", [
            {
                "app_id": item.app_id,
                "enabled": item.enabled
            }
            for item in self.app_list
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
            self.save_app_list()

    def set_app_enable(self, app_id: str, enabled: bool) -> None:
        """
        设置应用是否启用

        Args:
            app_id: 应用ID
            enabled: 是否启用
        """
        changed = False
        app_list = self.app_list
        for item in app_list:
            if item.app_id == app_id:
                if item.enabled != enabled:
                    changed = True
                    item.enabled = enabled
                break

        if changed:
            self.save_app_list()

    def set_app_order(self, app_id_list: list[str]) -> None:
        """
        设置应用运行顺序

        Args:
            app_id_list: 应用ID列表
        """
        old_list = self.app_list
        app_map: dict[str, ApplicationGroupConfigItem] = {}
        for item in old_list:
            app_map[item.app_id] = item

        new_list: list[ApplicationGroupConfigItem] = [
            app_map[app_id]
            for app_id in app_id_list
            if app_id in app_map
        ]
        for item in old_list:
            if item.app_id not in app_id_list:
                new_list.append(item)

        self.app_list = new_list
        self.save_app_list()

    def move_up_app(self, app_id: str) -> None:
        """
        将一个app的执行顺序往前调一位
        Args:
            app_id: 应用ID
        """
        idx = -1

        for i in range(len(self.app_list)):
            if self.app_list[i].app_id == app_id:
                idx = i
                break

        if idx <= 0:  # 无法交换
            return

        temp = self.app_list[idx - 1]
        self.app_list[idx - 1] = self.app_list[idx]
        self.app_list[idx] = temp

        self.save_app_list()
