from one_dragon.base.config.yaml_config import YamlConfig


class PipConfig(YamlConfig):
    """画中画窗口配置，保存窗口尺寸、位置和开关状态。"""

    def __init__(self) -> None:
        YamlConfig.__init__(self, 'pip')

    @property
    def enabled(self) -> bool:
        return self.get('enabled', False)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.update('enabled', value)

    @property
    def width(self) -> int:
        return self.get('width', 480)

    @width.setter
    def width(self, value: int) -> None:
        self.update('width', value)

    @property
    def x(self) -> int:
        return self.get('x', -1)

    @x.setter
    def x(self, value: int) -> None:
        self.update('x', value)

    @property
    def y(self) -> int:
        return self.get('y', -1)

    @y.setter
    def y(self, value: int) -> None:
        self.update('y', value)
