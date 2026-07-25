import os

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.utils import os_utils


class ApplicationGroupConfigItem:

    def __init__(self, app_id: str, enabled: bool, is_persisted: bool = True):
        """
        应用组配置项

        Args:
            app_id: 应用ID
            enabled: 是否启用
            is_persisted: 是否已进入用户保存的应用顺序
        """
        self.app_id: str = app_id
        self.enabled: bool = enabled
        self.is_persisted: bool = is_persisted
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
                "config", f"{instance_idx:02d}", group_id
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
        """保存已持久化的应用列表，并同步其显示顺序。"""
        persisted_apps = [item for item in self.app_list if item.is_persisted]

        # 将已持久化应用的排序同步回 _all_apps，未注册的应用保持原位
        active_set = {item.app_id for item in persisted_apps}
        active_indices = [i for i, item in enumerate(self._all_apps) if item.app_id in active_set]
        for idx, item in zip(active_indices, persisted_apps, strict=True):
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

        在 _all_apps 中保留所有已保存配置项（含未注册的），保持原有顺序。
        新注册的应用按默认顺序显示在头部，初始为禁用状态，但不立即保存。
        app_list 包含已注册的已保存项和未保存新项。

        Args:
            app_id_list: 当前已注册的应用ID列表
        """
        registered_set = set(app_id_list)
        persisted_ids = {item.app_id for item in self._all_apps}
        transient_map = {
            item.app_id: item
            for item in self.app_list
            if not item.is_persisted
        }

        transient_items: list[ApplicationGroupConfigItem] = []
        for app_id in app_id_list:
            if app_id not in persisted_ids:
                transient_items.append(
                    transient_map.get(app_id)
                    or ApplicationGroupConfigItem(
                        app_id=app_id,
                        enabled=False,
                        is_persisted=False,
                    )
                )

        persisted_items = [
            item for item in self._all_apps if item.app_id in registered_set
        ]
        self.app_list = transient_items + persisted_items

    def _persist_app_item(self, item: ApplicationGroupConfigItem) -> bool:
        """将运行时临时应用加入用户保存顺序。"""
        if item.is_persisted:
            return False

        item.is_persisted = True
        self._all_apps.append(item)
        return True

    def persist_app(self, app_id: str) -> None:
        """
        持久化指定应用当前的显示位置。

        Args:
            app_id: 应用ID
        """
        for item in self.app_list:
            if item.app_id == app_id and self._persist_app_item(item):
                self.save_app_list()
                return

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
                if enabled:
                    changed = self._persist_app_item(item) or changed
                if item.enabled != enabled:
                    changed = True
                    item.enabled = enabled
                break

        if changed:
            self.save_app_list()

    def remove_app(self, app_id: str) -> None:
        """从应用组配置中永久移除应用。"""
        old_all_apps = self._all_apps
        self._all_apps = [item for item in old_all_apps if item.app_id != app_id]
        self.app_list = [item for item in self.app_list if item.app_id != app_id]

        if len(self._all_apps) != len(old_all_apps):
            self.save_app_list()

    def set_app_order(self, app_id_list: list[str]) -> None:
        """
        设置应用运行顺序，并将当前列表中的临时应用纳入保存顺序。

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
        for item in self.app_list:
            self._persist_app_item(item)
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
