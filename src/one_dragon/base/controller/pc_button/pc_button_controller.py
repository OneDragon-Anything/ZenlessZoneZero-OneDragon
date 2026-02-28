import time
from typing import Optional


class PcButtonController:

    def __init__(self):
        self.key_press_time: float = 0.02

    def tap(self, key: str) -> None:
        """
        按键
        """
        pass

    def tap_combo(self, keys: list[str]) -> None:
        """同时按下多个键，等待后全部释放。

        :param keys: 按键列表，如 ['xbox_6', 'xbox_0'] 表示 LB+A
        """
        if not keys:
            return
        for key in keys:
            if key is not None:
                self.press(key, press_time=None)
        time.sleep(self.key_press_time)
        for key in keys:
            if key is not None:
                self.release(key)

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
