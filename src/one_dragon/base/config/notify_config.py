from one_dragon.base.config.yaml_config import YamlConfig


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

    def is_app_notify_enabled(self, app_id: str) -> bool:
        """
        获取指定 app_id 是否开启了通知
        如果 app_id 为空或在配置中未找到，默认返回 True
        """
        if not app_id:
            return True
        return self.get(app_id, True)

    def _generate_dynamic_properties(self):
        # 为 app_map 中的每个 app_id 动态生成 property，便于通过属性访问和更新配置
        for app_id in self.app_map:
            def create_getter(name: str):
                def getter(self) -> bool:
                    return self.get(name, True)
                return getter

            def create_setter(name: str):
                def setter(self, new_value: bool) -> None:
                    self.update(name, new_value)
                return setter

            prop = property(create_getter(app_id), create_setter(app_id))
            setattr(self.__class__, app_id, prop)
