class ContextLazySignal:
    """
    用于存储懒加载的信号状态
    """
    def __init__(self):
        self._signals = {}

    @property
    def reload_banner(self) -> bool:
        """
        刷新主页背景
        """
        return self._signals.get('reload_banner', False)

    @reload_banner.setter
    def reload_banner(self, new_value: bool) -> None:
        self._signals['reload_banner'] = new_value

    @property
    def start_onedragon(self) -> bool:
        """
        启动一条龙
        """
        return self._signals.get('start_onedragon', False)

    @start_onedragon.setter
    def start_onedragon(self, new_value: bool) -> None:
        self._signals['start_onedragon'] = new_value
