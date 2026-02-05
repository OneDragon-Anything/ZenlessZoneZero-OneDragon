from typing import Optional


class PcButtonController:

    def __init__(self):
        self.key_press_time: float = 0.02
        self.input_enabled: bool = True

    def disable_input(self) -> None:
        self.input_enabled = False

    def enable_input(self) -> None:
        self.input_enabled = True

    def tap(self, key: str) -> None:
        """
        按键
        """
        pass

    def press(self, key: str, press_time: Optional[float] = None) -> None:
        """
        :param key: 按键
        :param press_time: 持续按键时间。不传入时 代表不松开
        :return:
        """
        pass

    def reset(self) -> None:
        """
        重置状态
        """
        pass

    def release(self, key: str) -> None:
        """
        施释放按键
        """
        pass

    def set_key_press_time(self, key_press_time: float) -> None:
        self.key_press_time = key_press_time
