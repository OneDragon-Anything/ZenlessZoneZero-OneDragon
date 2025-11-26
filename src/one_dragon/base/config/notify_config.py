from one_dragon.base.config.yaml_config import YamlConfig


class NotifyLevel:
    OFF = 0
    APP = 1
    ALL = 2


class NotifyConfig(YamlConfig):

    def __init__(self, instance_idx: int, app_map: dict[str, str]):
        YamlConfig.__init__(self, 'notify', instance_idx=instance_idx)
        self.app_map = app_map.copy()
        self._generate_dynamic_properties()

    @property
    def title(self) -> str:
        return self.get('title', '一条龙运行通知')

    @title.setter
    def title(self, new_value: str) -> None:
        self.update('title', new_value)

    @property
    def enable_notify(self) -> bool:
        return self.get('enable_notify', True)

    @enable_notify.setter
    def enable_notify(self, new_value: bool) -> None:
        self.update('enable_notify', new_value)

    @property
    def enable_before_notify(self) -> bool:
        return self.get('enable_before_notify', True)

    @enable_before_notify.setter
    def enable_before_notify(self, new_value: bool) -> None:
        self.update('enable_before_notify', new_value)

    def get_app_notify_level(self, app_id: str) -> int:
        """
        获取指定 app_id 的通知等级
        0: 关闭
        1: 仅应用
        2: 全部（应用和节点）
        """
        if not app_id:
            return NotifyLevel.ALL

        return int(self.get(app_id, NotifyLevel.ALL))

    def _generate_dynamic_properties(self):
        # 为 app_map 中的每个 app_id 动态生成 property，便于通过属性访问和更新配置
        for app_id in self.app_map:
            def create_getter(name: str):
                def getter(self) -> int:
                    return self.get_app_notify_level(name)
                return getter

            def create_setter(name: str):
                def setter(self, new_value: int) -> None:
                    self.update(name, new_value)
                return setter

            prop = property(create_getter(app_id), create_setter(app_id))
            setattr(self.__class__, app_id, prop)
