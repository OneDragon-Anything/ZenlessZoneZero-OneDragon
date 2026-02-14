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
        self._all_apps: list[ApplicationGroupConfigItem] = []  # 完整有序列表（含未注册的）
        self.app_list: list[ApplicationGroupConfigItem] = []   # 已注册的应用（过滤视图）

        self._init_app_list()

    def _init_app_list(self) -> None:
        dict_list = self.get("app_list", [])
        for item in dict_list:
            self._all_apps.append(
                ApplicationGroupConfigItem(
                    app_id=item.get("app_id", ""),
                    enabled=item.get("enabled", False),
                )
            )

    def save_app_list(self) -> None:
        """保存应用列表，同步 app_list 排序到 _all_apps 后写入文件"""
        # 将 app_list 的排序同步回 _all_apps，未注册的应用保持原位
        active_set = {item.app_id for item in self.app_list}
        active_indices = [i for i, item in enumerate(self._all_apps) if item.app_id in active_set]
        for idx, item in zip(active_indices, self.app_list, strict=True):
            self._all_apps[idx] = item

        self.update("app_list", [
            {
                "app_id": item.app_id,
                "enabled": item.enabled
            }
            for item in self._all_apps
        ])

    def update_full_app_list(self, app_id_list: list[str]) -> None:
        """
        更新完整的应用ID列表
        只应该被默认组使用 用于填充一条龙默认应用

        在 _all_apps 中保留所有配置项（含未注册的），保持原有顺序。
        新注册的应用追加到末尾。app_list 只包含已注册的应用。

        Args:
            app_id_list: 当前已注册的应用ID列表
        """
        registered_set = set(app_id_list)
        seen: set[str] = {item.app_id for item in self._all_apps}

        # 追加新注册但不在配置中的应用
        changed = False
        for app_id in app_id_list:
            if app_id not in seen:
                seen.add(app_id)
                self._all_apps.append(ApplicationGroupConfigItem(app_id=app_id, enabled=False))
                changed = True

        # 从 _all_apps 中过滤出已注册的应用
        self.app_list = [item for item in self._all_apps if item.app_id in registered_set]

        if changed:
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

    def move_top_app(self, app_id: str) -> None:
        """
        将一个app的执行顺序置顶（移到最前面）
        Args:
            app_id: 应用ID
        """
        idx = -1

        for i in range(len(self.app_list)):
            if self.app_list[i].app_id == app_id:
                idx = i
                break

        if idx <= 0:  # 已经在第一位
            return

        # 移除并插入到开头
        app = self.app_list.pop(idx)
        self.app_list.insert(0, app)

        self.save_app_list()
