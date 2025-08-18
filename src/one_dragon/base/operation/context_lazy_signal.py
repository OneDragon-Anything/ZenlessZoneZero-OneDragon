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

    @property
    def notice_card_config_changed(self) -> bool:
        """
        公告卡片配置发生变化
        """
        return self._signals.get('notice_card_config_changed', False)

    @notice_card_config_changed.setter
    def notice_card_config_changed(self, new_value: bool) -> None:
        self._signals['notice_card_config_changed'] = new_value
