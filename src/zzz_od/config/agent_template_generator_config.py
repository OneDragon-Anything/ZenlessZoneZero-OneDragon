from one_dragon.base.config.yaml_config import YamlConfig


class AgentTemplateGeneratorConfig(YamlConfig):
    """代理人模板生成工具配置，保存快捷键和悬浮窗位置。"""

    def __init__(self) -> None:
        YamlConfig.__init__(self, 'agent_template_generator')

    def get_hotkey(self, action: str, default_value: str) -> str:
        value = self.get(f'hotkey_{action}', default_value)
        return value if isinstance(value, str) else default_value

    def set_hotkey(self, action: str, value: str) -> None:
        self.update(f'hotkey_{action}', value)

    @property
    def float_enabled(self) -> bool:
        return self.get('float_enabled', True)

    @float_enabled.setter
    def float_enabled(self, value: bool) -> None:
        self.update('float_enabled', value)

    @property
    def float_expanded(self) -> bool:
        return self.get('float_expanded', False)

    @float_expanded.setter
    def float_expanded(self, value: bool) -> None:
        self.update('float_expanded', value)

    @property
    def float_x(self) -> int:
        return self.get('float_x', -1)

    @float_x.setter
    def float_x(self, value: int) -> None:
        self.update('float_x', value)

    @property
    def float_y(self) -> int:
        return self.get('float_y', -1)

    @float_y.setter
    def float_y(self, value: int) -> None:
        self.update('float_y', value)
