from one_dragon.base.config.yaml_config import YamlConfig


class SuibianTempleConfig(YamlConfig):
    """
    随便观配置类
    管理随便观地点各个功能的开关状态
    """

    def __init__(self, instance_idx: int):
        """
        初始化随便观配置
        :param instance_idx: 实例索引
        """
        YamlConfig.__init__(self, 'suibian_temple', instance_idx=instance_idx)

    @property
    def overall_enabled(self) -> bool:
        """
        总开关 - 控制是否执行任何随便观功能
        :return: 总开关状态
        """
        return self.get('overall_enabled', True)

    @overall_enabled.setter
    def overall_enabled(self, new_value: bool) -> None:
        """
        设置总开关状态
        :param new_value: 新的开关状态
        """
        self.update('overall_enabled', new_value)

    @property
    def adventure_squad_enabled(self) -> bool:
        """
        小队游历功能开关
        :return: 小队游历开关状态
        """
        return self.get('adventure_squad_enabled', True)

    @adventure_squad_enabled.setter
    def adventure_squad_enabled(self, new_value: bool) -> None:
        """
        设置小队游历开关状态
        :param new_value: 新的开关状态
        """
        self.update('adventure_squad_enabled', new_value)

    @property
    def craft_enabled(self) -> bool:
        """
        制造坊功能开关
        :return: 制造坊开关状态
        """
        return self.get('craft_enabled', True)

    @craft_enabled.setter
    def craft_enabled(self, new_value: bool) -> None:
        """
        设置制造坊开关状态
        :param new_value: 新的开关状态
        """
        self.update('craft_enabled', new_value)

    @property
    def yum_cha_sin_enabled(self) -> bool:
        """
        饮茶仙功能开关
        :return: 饮茶仙开关状态
        """
        return self.get('yum_cha_sin_enabled', True)

    @yum_cha_sin_enabled.setter
    def yum_cha_sin_enabled(self, new_value: bool) -> None:
        """
        设置饮茶仙开关状态
        :param new_value: 新的开关状态
        """
        self.update('yum_cha_sin_enabled', new_value)

    @property
    def boobox_enabled(self) -> bool:
        """
        邦巢功能开关
        :return: 邦巢开关状态
        """
        return self.get('boobox_enabled', True)

    @boobox_enabled.setter
    def boobox_enabled(self, new_value: bool) -> None:
        """
        设置邦巢开关状态
        :param new_value: 新的开关状态
        """
        self.update('boobox_enabled', new_value)

    def reset_to_default(self) -> None:
        """
        重置所有配置为默认值
        """
        self.overall_enabled = True
        self.adventure_squad_enabled = True
        self.craft_enabled = True
        self.yum_cha_sin_enabled = True
        self.boobox_enabled = True